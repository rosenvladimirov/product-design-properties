# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
from odoo import Command
from odoo.tests import tagged

from odoo.addons.sale_order_poc_mrp.tests.common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestPocKitOption(PocMrpCommon):
    """Отметка в конфигурацията включва или маха фантомен кит от MO."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.led = Product.create(
            {"name": "POC LED", "type": "consu", "is_storable": True}
        )
        cls.kit = Product.create({"name": "POC LED Kit", "type": "consu"})
        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.kit.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "phantom",
                "bom_line_ids": [
                    Command.create({"product_id": cls.led.id, "product_qty": 4.0})
                ],
            }
        )
        cls.bom.bom_line_ids = [
            Command.create({"product_id": cls.kit.id, "product_qty": 1.0})
        ]
        cls.line_kit = cls.bom.bom_line_ids.filtered(
            lambda l: l.product_id == cls.kit
        )
        cls.p_kit = cls.env["sale.order.poc.param"].create(
            {"code": "t_kit_led", "name": "LED Kit", "param_type": "boolean"}
        )
        cls.template.line_ids = [Command.create({"param_id": cls.p_kit.id})]

    def _kit_formula(self, formula="skip = not t_kit_led"):
        self.line_kit.formula_template_id = self.env[
            "mrp.bom.line.formula.template"
        ].create({"name": "POC kit option", "quantity_formula": formula})

    def _order_with_kit(self, checked, qty=10.0):
        order = self._make_order(qty=qty)
        poc = self._fill(self._make_poc(order))
        poc._poc_set_params({"t_kit_led": checked})
        order.action_confirm()
        return poc.production_ids

    def test_checked_kit_is_in_the_order(self):
        self._kit_formula()
        production = self._order_with_kit(True)
        # 4 LED на кит × 10
        self.assertAlmostEqual(self._raw(production, self.led).product_uom_qty, 40.0)
        # останалите редове не са пипнати
        self.assertAlmostEqual(self._raw(production, self.ink).product_uom_qty, 10.0)

    def test_unchecked_kit_leaves_the_order(self):
        self._kit_formula()
        production = self._order_with_kit(False)
        self.assertFalse(self._raw(production, self.led))
        self.assertAlmostEqual(self._raw(production, self.ink).product_uom_qty, 10.0)

    def test_zero_quantity_leaves_the_order(self):
        self._kit_formula("result = 1 if t_kit_led else 0")
        production = self._order_with_kit(False)
        self.assertFalse(self._raw(production, self.led))

    def test_kit_without_formula_stays(self):
        production = self._order_with_kit(False)
        self.assertAlmostEqual(self._raw(production, self.led).product_uom_qty, 40.0)

    def test_broken_formula_keeps_the_kit(self):
        """Грешка във формула не спира поръчката (ADR sale-order-poc/0006)."""
        self._kit_formula("skip = not t_missing")
        production = self._order_with_kit(False)
        self.assertAlmostEqual(self._raw(production, self.led).product_uom_qty, 40.0)

    def test_order_without_configuration_keeps_the_kit(self):
        self._kit_formula()
        production = self.env["mrp.production"].create(
            {"product_id": self.product.id, "product_qty": 10.0, "bom_id": self.bom.id}
        )
        self.assertFalse(production.poc_id)
        self.assertAlmostEqual(self._raw(production, self.led).product_uom_qty, 40.0)

    def test_bom_structure_outside_production_is_standard(self):
        """Без MO в контекста формулата на кита не се пуска."""
        self._kit_formula()
        _boms, lines = self.bom.explode(self.product, 1.0)
        self.assertIn(self.led, [line.product_id for line, _data in lines])

    def test_changing_the_configuration_follows_the_kit(self):
        """Потвърдена незапочната MO следва конфигурацията (ADR 0008)."""
        self._kit_formula()
        production = self._order_with_kit(False)
        self.assertFalse(self._raw(production, self.led))
        poc = production.poc_id
        poc.with_user(self.manager).write(
            {"params": {**(poc.params._values or {}), "t_kit_led": True}}
        )
        self.assertAlmostEqual(self._raw(production, self.led).product_uom_qty, 40.0)
        poc.with_user(self.manager).write(
            {"params": {**(poc.params._values or {}), "t_kit_led": False}}
        )
        # потвърдена MO не трие движение, а го пуска на 0 (_poc_apply_explosion)
        self.assertAlmostEqual(
            sum(self._raw(production, self.led).mapped("product_uom_qty")), 0.0
        )

    # ── Генераторът на опциите ───────────────────────────────────────

    def test_generator_makes_checkbox_line_and_formula(self):
        self.kit.default_code = "LED-KIT 1"
        action = self.bom.action_poc_kit_options()
        self.assertEqual(action["params"]["type"], "success")
        param = self.env["sale.order.poc.param"].search([("code", "=", "kit_led_kit_1")])
        self.assertEqual(param.param_type, "boolean")
        self.assertIn(param, self.template.line_ids.param_id)
        self.assertEqual(self.line_kit.quantity_formula, "skip = not kit_led_kit_1")
        # редовете без кит не получават формула
        self.assertFalse(self.line_film.quantity_formula)
        self.assertFalse(self.line_ink.quantity_formula)

    def test_generator_runs_twice_without_duplicates(self):
        self.kit.default_code = "LED"
        self.bom.action_poc_kit_options()
        self.bom.action_poc_kit_options()
        self.assertEqual(
            self.env["sale.order.poc.param"].search_count([("code", "=", "kit_led")]), 1
        )
        self.assertEqual(
            len(self.template.line_ids.filtered(lambda l: l.code == "kit_led")), 1
        )

    def test_generator_keeps_a_foreign_formula(self):
        self._kit_formula("result = 2")
        action = self.bom.action_poc_kit_options()
        self.assertEqual(action["params"]["type"], "warning")
        self.assertEqual(self.line_kit.quantity_formula, "result = 2")

    def test_generated_option_drives_the_order(self):
        """Цялата верига: генератор → отметка в POC → кит в MO или не."""
        self.kit.default_code = "LED"
        self.bom.action_poc_kit_options()
        order = self._make_order(qty=10.0)
        poc = self._fill(self._make_poc(order))
        poc._poc_set_params({"kit_led": False})
        order.action_confirm()
        self.assertFalse(self._raw(poc.production_ids, self.led))

    def test_generator_keeps_twin_kits_apart(self):
        """``A#`` е друг кит от ``A``: две отметки, не една (uat-mec, 10.10)."""
        self.kit.default_code = "KIT-Piezo_PIC"
        twin = self.env["product.product"].create(
            {"name": "POC LED Kit twin", "type": "consu", "default_code": "KIT-Piezo_PIC#"}
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": twin.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "phantom",
                "bom_line_ids": [
                    Command.create({"product_id": self.led.id, "product_qty": 1.0})
                ],
            }
        )
        self.bom.bom_line_ids = [Command.create({"product_id": twin.id, "product_qty": 1.0})]
        line_twin = self.bom.bom_line_ids.filtered(lambda l: l.product_id == twin)
        self.bom.action_poc_kit_options()
        self.assertEqual(self.line_kit.quantity_formula, "skip = not kit_piezo_pic")
        self.assertEqual(line_twin.quantity_formula, "skip = not kit_piezo_pic_alt")

    def test_generator_code_clash_gets_the_product_id(self):
        """Две референции, които се изчистват до един код, не делят отметка."""
        self.kit.default_code = "LED.1"
        other = self.env["sale.order.poc.param"].create(
            {"code": "kit_led_1", "name": "Some other kit", "param_type": "boolean"}
        )
        self.bom.action_poc_kit_options()
        self.assertEqual(
            self.line_kit.quantity_formula, "skip = not kit_led_1_%s" % self.kit.id
        )
        self.assertEqual(other.name, "Some other kit")
