# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
from psycopg2.errors import UniqueViolation

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestFormulaEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env["formula.template"]  # носи formula.engine.mixin

    # ── Валидация ────────────────────────────────────────────────────

    def test_check_valid_formula(self):
        self.assertFalse(self.engine._formula_check("result = a + b"))

    def test_check_empty_formula(self):
        self.assertFalse(self.engine._formula_check(False))
        self.assertFalse(self.engine._formula_check(""))

    def test_check_invalid_formula(self):
        # синтактична грешка → съобщение, не False
        self.assertTrue(self.engine._formula_check("result = = 1"))

    def test_check_dunder_name_returns_message(self):
        # забранено име (dunder) → съобщение, НЕ гол NameError
        # (core test_python_expr не хваща NameError от assert_no_dunder_name)
        self.assertTrue(self.engine._formula_check("net__total = 1"))

    def test_constraint_rejects_invalid_formula(self):
        with self.assertRaises(ValidationError):
            self.engine.create(
                {"name": "Broken", "formula": "result = = 1"}
            )

    # ── Изпълнение ───────────────────────────────────────────────────

    def test_eval_single_output(self):
        out = self.engine._formula_eval(
            "result = base * rate", {"base": 1000.0, "rate": 0.1}
        )
        self.assertEqual(out, {"result": 100.0})

    def test_eval_multiple_outputs_partial(self):
        # обявен, но незададен изход просто липсва в резултата
        out = self.engine._formula_eval(
            "amount = 5\nqty = 2",
            {},
            outputs=("amount", "qty", "rate"),
        )
        self.assertEqual(out, {"amount": 5, "qty": 2})

    def test_eval_mutates_context_in_place(self):
        # Odoo 19+ safe_eval мутира контекста — извикващият вижда
        # и необявените променливи след изпълнението
        values = {"a": 1}
        self.engine._formula_eval("b = a + 1", values, outputs=())
        self.assertEqual(values.get("b"), 2)

    def test_eval_error_propagates(self):
        # БЕЗ вградена fallback политика: грешката стига до извикващия
        with self.assertRaises(Exception):
            self.engine._formula_eval("result = 1 / 0", {})

    def test_eval_no_builtin_escape(self):
        # safe_eval пази пясъчника: опасни конструкции гърмят
        with self.assertRaises(Exception):
            self.engine._formula_eval(
                "result = __import__('os').getcwd()", {}
            )

    # ── Strict режим (payroll паттернът) ─────────────────────────────

    def test_strict_missing_output_raises(self):
        # твърд fail: формулата не присвоява обявения изход
        with self.assertRaises(ValueError):
            self.engine._formula_eval(
                "res = base * 2", {"base": 10}, strict=True
            )

    def test_strict_pops_stale_output(self):
        # stale стойност от предишна итерация НЕ минава за резултат:
        # strict маха обявените изходи преди изпълнението
        values = {"base": 10, "result": 500.0}
        with self.assertRaises(ValueError):
            self.engine._formula_eval("res = base * 2", values, strict=True)
        self.assertNotIn("result", values)

    def test_strict_assigned_output_returned(self):
        out = self.engine._formula_eval(
            "result = base * 2", {"base": 10, "result": 500.0}, strict=True
        )
        self.assertEqual(out, {"result": 20})

    # ── Шаблони ──────────────────────────────────────────────────────

    def test_template_evaluate(self):
        template = self.engine.create(
            {
                "name": "Net amount",
                "code": "TST_NET",
                "usage": "test",
                "formula": "result = gross - deductions",
            }
        )
        out = template.evaluate({"gross": 1500.0, "deductions": 300.0})
        self.assertEqual(out, {"result": 1200.0})

    def test_get_by_code_company_priority(self):
        company = self.env.company
        glob = self.engine.create(
            {
                "name": "Global",
                "code": "TST_PRIO",
                "company_id": False,
                "formula": "result = 1",
            }
        )
        self.assertEqual(self.engine.get_by_code("TST_PRIO"), glob)
        specific = self.engine.create(
            {
                "name": "Company specific",
                "code": "TST_PRIO",
                "company_id": company.id,
                "formula": "result = 2",
            }
        )
        self.assertEqual(self.engine.get_by_code("TST_PRIO"), specific)
        self.assertEqual(
            self.engine.get_by_code("TST_PRIO", company=company), specific
        )

    def test_get_by_code_missing(self):
        self.assertFalse(self.engine.get_by_code("TST_MISSING"))

    @mute_logger("odoo.sql_db")
    def test_code_unique_per_company(self):
        vals = {
            "name": "Dup",
            "code": "TST_DUP",
            "company_id": self.env.company.id,
            "formula": "result = 1",
        }
        self.engine.create(vals)
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint():
            self.engine.create(vals)

    @mute_logger("odoo.sql_db")
    def test_code_unique_global(self):
        # PG NULL-distinct дупката е затворена с частичен уникален индекс:
        # два глобални шаблона със същия code не се допускат
        vals = {
            "name": "Dup global",
            "code": "TST_DUP_GLOB",
            "company_id": False,
            "formula": "result = 1",
        }
        self.engine.create(vals)
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint():
            self.engine.create(vals)

    def test_copy_drops_code(self):
        # Duplicate не бива да произвежда втори запис със същия code
        template = self.engine.create(
            {"name": "Orig", "code": "TST_COPY", "formula": "result = 1"}
        )
        self.assertFalse(template.copy().code)
