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
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestAspectsAndTables(PocCommon):
    """Аспекти и таблици: разширенията на носителя (ADR sale-order-poc/0004)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env["sale.order.poc.param"]
        cls.p_print_colors = Param.create(
            {"code": "t_print_colors", "name": "Print Colors", "param_type": "integer"}
        )
        cls.p_print_cost = Param.create(
            {"code": "t_print_cost", "name": "Print Cost", "param_type": "float"}
        )
        cls.p_recipe = Param.create(
            {"code": "t_recipe", "name": "Recipe", "param_type": "table"}
        )
        cls.aspect_print = cls.env["sale.order.poc.template"].create(
            {
                "code": "t_print",
                "name": "Printing",
                "usage": "aspect",
                "line_ids": [
                    Command.create({"sequence": 1, "param_id": cls.p_print_colors.id}),
                    Command.create(
                        {
                            "sequence": 2,
                            "param_id": cls.p_print_cost.id,
                            # чете параметър на ОСНОВНИЯ шаблон: пространството
                            # на формулите е едно
                            "formula": "result = t_print_colors * t_width_mm / 1000",
                        }
                    ),
                ],
            }
        )
        cls.template.allowed_aspect_ids = [Command.link(cls.aspect_print.id)]

    def _aspect(self, poc, template=None, **params):
        aspect = self.env["sale.order.poc.aspect"].create(
            {"poc_id": poc.id, "template_id": (template or self.aspect_print).id}
        )
        if params:
            poc._poc_set_params(params)
            poc._poc_compute_derived()
        return aspect

    # ── Аспекти ──────────────────────────────────────────────────────

    def test_overlapping_code_is_refused(self):
        """Аспект не може да повтори код от основния шаблон."""
        clash = self.env["sale.order.poc.template"].create(
            {
                "code": "t_clash",
                "name": "Clash",
                "usage": "aspect",
                "line_ids": [Command.create({"param_id": self.p_width.id})],
            }
        )
        with self.assertRaises(ValidationError):
            self.template.allowed_aspect_ids = [Command.link(clash.id)]

    def test_aspect_values_are_in_one_space(self):
        """Формулата на аспекта чете параметър на основния шаблон."""
        poc = self._fill(self._make_poc())
        self._aspect(poc, t_print_colors=4)
        values = poc._poc_values()
        self.assertEqual(values["t_print_colors"], 4)
        # 4 × 300 / 1000
        self.assertAlmostEqual(values["t_print_cost"], 1.2)
        self.assertEqual(poc.aspect_ids.param_origins, {"t_print_cost": "formula"})
        # основният контейнер не знае за параметрите на аспекта
        self.assertNotIn("t_print_colors", poc.params._values or {})

    def test_default_aspects_are_born_with_the_configuration(self):
        self.template.default_aspect_ids = [Command.link(self.aspect_print.id)]
        poc = self._make_poc()
        self.assertEqual(poc.aspect_ids.template_id, self.aspect_print)

    def test_default_aspect_must_be_allowed(self):
        other = self.env["sale.order.poc.template"].create(
            {"code": "t_other", "name": "Other", "usage": "aspect"}
        )
        with self.assertRaises(ValidationError):
            self.template.default_aspect_ids = [Command.link(other.id)]

    def test_aspect_of_another_template_is_refused(self):
        poc = self._make_poc()
        other = self.env["sale.order.poc.template"].create(
            {"code": "t_label", "name": "Label", "usage": "aspect"}
        )
        with self.assertRaises(ValidationError):
            self._aspect(poc, template=other)

    def test_aspect_appears_once(self):
        poc = self._make_poc()
        self._aspect(poc)
        with self.assertRaises(Exception):
            self._aspect(poc)

    def test_confirmed_aspect_is_locked_for_the_salesman(self):
        poc = self._fill(self._make_poc())
        aspect = self._aspect(poc, t_print_colors=2)
        poc.sale_line_id.order_id.action_confirm()
        with self.assertRaises(UserError):
            aspect.with_user(self.salesman).write(
                {"params": {**(aspect.params._values or {}), "t_print_colors": 6}}
            )
        aspect.with_user(self.manager).write(
            {"params": {**(aspect.params._values or {}), "t_print_colors": 6}}
        )
        self.assertEqual(poc._poc_values()["t_print_colors"], 6)
        self.assertAlmostEqual(poc._poc_values()["t_print_cost"], 1.8)

    # ── Таблици ──────────────────────────────────────────────────────

    def test_table_is_not_a_property(self):
        """Таблицата обявява редове, не влиза в схемата на пропъртитата."""
        self.template.line_ids = [Command.create({"param_id": self.p_recipe.id})]
        names = [entry["name"] for entry in self.template.param_definition]
        self.assertNotIn("t_recipe", names)
        self.assertIn("t_width_mm", names)

    def test_table_is_a_list_in_the_contract(self):
        self.template.line_ids = [Command.create({"param_id": self.p_recipe.id})]
        poc = self._fill(self._make_poc())
        self.assertEqual(poc._poc_values()["t_recipe"], [])
        self.env["sale.order.poc.line"].create(
            [
                {
                    "poc_id": poc.id,
                    "param_id": self.p_recipe.id,
                    "sequence": 2,
                    "key": "outer",
                    "product_id": self.product.id,
                    "value": 3.5,
                    "uom_id": self.product.uom_id.id,
                },
                {
                    "poc_id": poc.id,
                    "param_id": self.p_recipe.id,
                    "sequence": 1,
                    "key": "inner",
                    "value": 1.0,
                },
            ]
        )
        rows = poc._poc_values()["t_recipe"]
        self.assertEqual([row["key"] for row in rows], ["inner", "outer"])
        self.assertEqual(rows[1]["product"], self.product)
        self.assertAlmostEqual(rows[1]["value"], 3.5)

    def test_formula_reads_the_table(self):
        total = self.env["sale.order.poc.param"].create(
            {"code": "t_recipe_total", "name": "Recipe Total", "param_type": "float"}
        )
        self.template.line_ids = [
            Command.create({"param_id": self.p_recipe.id}),
            Command.create(
                {
                    "param_id": total.id,
                    "formula": "result = sum(row['value'] for row in t_recipe)",
                }
            ),
        ]
        poc = self._fill(self._make_poc())
        self.env["sale.order.poc.line"].create(
            [
                {"poc_id": poc.id, "param_id": self.p_recipe.id, "value": 2.0},
                {"poc_id": poc.id, "param_id": self.p_recipe.id, "value": 5.0},
            ]
        )
        self.assertAlmostEqual(poc._poc_values()["t_recipe_total"], 7.0)

    def test_table_row_needs_its_table(self):
        poc = self._fill(self._make_poc())
        with self.assertRaises(ValidationError):
            self.env["sale.order.poc.line"].create(
                {"poc_id": poc.id, "param_id": self.p_recipe.id, "value": 1.0}
            )

    def test_table_parameter_has_no_formula(self):
        with self.assertRaises(ValidationError):
            self.template.line_ids = [
                Command.create({"param_id": self.p_recipe.id, "formula": "result = 1"})
            ]
