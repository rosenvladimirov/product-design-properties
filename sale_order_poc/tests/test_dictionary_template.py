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
from odoo.exceptions import UserError, ValidationError
from odoo.fields import PropertiesDefinition
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestDictionaryTemplate(PocCommon):
    def test_code_rules(self):
        """Кодът е име на променлива: регулярен израз, не ключова дума, не
        резервирано име на договора."""
        Param = self.env["sale.order.poc.param"]
        for code in ("Width", "2width", "width-mm", "class", "product", "quantity"):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                Param.create({"code": code, "name": code, "param_type": "float"})

    def test_used_code_and_type_are_frozen(self):
        """Смяна на кода или типа на използван параметър е забранена."""
        with self.assertRaises(UserError):
            self.p_width.code = "t_width_cm"
        with self.assertRaises(UserError):
            self.p_width.param_type = "integer"
        self.p_width.name = "Width (outer)"  # етикетът се мени свободно

    def test_definition_has_only_allowed_keys(self):
        """Изчислената схема носи само позволените ключове на ядрото.

        Ключ извън тях сваля зареждането на базата.
        """
        allowed = set(PropertiesDefinition.ALLOWED_KEYS)
        definition = self.template.param_definition
        self.assertTrue(definition)
        for entry in definition:
            self.assertLessEqual(set(entry), allowed, entry)
        names = [entry["name"] for entry in definition]
        self.assertEqual(names[0], "section_0")
        self.assertIn("t_weight_g", names)
        tags = next(e for e in definition if e["name"] == "t_colors")["tags"]
        # таговете са тройки: двойка сваля валидацията
        self.assertTrue(all(len(tag) == 3 for tag in tags))
        material = next(e for e in definition if e["name"] == "t_material")
        self.assertEqual(material["selection"], [["ldpe", "LDPE"], ["hdpe", "HDPE"]])

    def test_new_line_appears_in_definition(self):
        """Параметър, добавен в шаблона, е в схемата веднага, без ъпгрейд."""
        extra = self.env["sale.order.poc.param"].create(
            {"code": "t_handles", "name": "Handles", "param_type": "boolean"}
        )
        self.template.write({"line_ids": [(0, 0, {"sequence": 50, "param_id": extra.id})]})
        self.assertIn(
            "t_handles", [e["name"] for e in self.template.param_definition]
        )

    def test_definition_cannot_be_written(self):
        """Схемата не се пише на ръка — така uuid ключ не се ражда."""
        with self.assertRaises(UserError):
            self.template.write(
                {"param_definition": [{"name": "abc", "type": "char", "string": "X"}]}
            )

    def test_widget_definition_change_is_refused(self):
        """Пътят на уиджета: списък с definition_changed пише схемата на
        шаблона с правата на потребителя — и мениджърът спира в пазача."""
        poc = self._make_poc()
        definition = [dict(entry) for entry in self.template.param_definition]
        definition.append(
            {"name": "x_new", "string": "New", "type": "char", "definition_changed": True}
        )
        with self.assertRaisesRegex(UserError, "template lines"):
            poc.with_user(self.manager).write({"params": definition})

    def test_formula_cycle_is_refused(self):
        """Цикъл между формулите дава грешка при запис на шаблона."""
        a = self.env["sale.order.poc.param"].create(
            {"code": "t_cycle_a", "name": "A", "param_type": "float"}
        )
        b = self.env["sale.order.poc.param"].create(
            {"code": "t_cycle_b", "name": "B", "param_type": "float"}
        )
        with self.assertRaises(ValidationError):
            self.env["sale.order.poc.template"].create(
                {
                    "code": "t_cycle",
                    "name": "Cycle",
                    "line_ids": [
                        (0, 0, {"param_id": a.id, "formula": "result = t_cycle_b + 1"}),
                        (0, 0, {"param_id": b.id, "formula": "result = t_cycle_a + 1"}),
                    ],
                }
            )

    def test_formula_order_follows_dependencies(self):
        """Брутото (sequence 10) зависи от нетото (sequence 11): нетото първо."""
        order = [line.param_id.code for line in self.template._poc_formula_lines()]
        self.assertEqual(order, ["t_weight_g", "t_weight_gross_g"])

    def test_manual_flags_need_a_formula(self):
        with self.assertRaises(ValidationError):
            self.template.line_ids.filtered(
                lambda line: line.param_id == self.p_width
            ).allow_manual = True
