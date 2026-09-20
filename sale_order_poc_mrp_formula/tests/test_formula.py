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
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sale_order_poc_mrp.tests.common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestPocFormula(PocMrpCommon):
    """Stage 2 с истинския двигател на PDP, без стъб."""

    def _formula(self, line, formula):
        line.formula_template_id = self.env["mrp.bom.line.formula.template"].create(
            {"name": "POC %s" % line.product_id.name, "quantity_formula": formula}
        )

    def test_formula_uses_the_configuration(self):
        self._formula(
            self.line_film,
            "result = t_width_mm * t_length_mm / 10000 * mo_qty + 5",
        )
        order, poc = self._confirmed_order(qty=10.0)
        # 300 × 500 / 10 000 × 10 + 5
        self.assertAlmostEqual(
            self._raw(poc.production_ids, self.film).product_uom_qty, 155.0
        )

    def test_selection_is_compared_by_key(self):
        """Селекцията идва като КЛЮЧ, не като етикет (LDPE срещу ldpe)."""
        self._formula(
            self.line_film,
            "result = 2 * mo_qty if t_material == 'ldpe' else 99",
        )
        order, poc = self._confirmed_order(qty=10.0)
        self.assertAlmostEqual(
            self._raw(poc.production_ids, self.film).product_uom_qty, 20.0
        )

    def test_helpers_are_available(self):
        self._formula(self.line_film, "result = ceil(t_width_mm / 200) * mo_qty")
        order, poc = self._confirmed_order(qty=10.0)
        # ceil(1.5) × 10
        self.assertAlmostEqual(
            self._raw(poc.production_ids, self.film).product_uom_qty, 20.0
        )

    def test_unknown_name_keeps_the_standard_quantity(self):
        """Грешка във формула не спира поръчката (ADR sale-order-poc/0006)."""
        self._formula(self.line_film, "result = t_missing * mo_qty")
        order, poc = self._confirmed_order(qty=10.0)
        # статичното от BoM: 2 × 10
        self.assertAlmostEqual(
            self._raw(poc.production_ids, self.film).product_uom_qty, 20.0
        )

    def test_check_reports_the_unknown_name(self):
        self._formula(self.line_film, "result = t_missing * mo_qty")
        with self.assertRaisesRegex(UserError, "t_missing"):
            self.bom.action_check_poc_formulas()

    def test_check_accepts_the_configuration_names(self):
        self._formula(
            self.line_film,
            "total = t_width_mm * t_length_mm\nresult = total / 10000 * mo_qty",
        )
        action = self.bom.action_check_poc_formulas()
        self.assertEqual(action["tag"], "display_notification")

    def test_table_becomes_extra_components(self):
        """Таблицата стига до производството през add_products (S0 + S2)."""
        recipe = self.env["sale.order.poc.param"].create(
            {"code": "t_recipe", "name": "Recipe", "param_type": "table"}
        )
        self.template.line_ids = [Command.create({"param_id": recipe.id})]
        self._formula(
            self.line_film,
            "result = 2 * mo_qty\n"
            "add_products = [\n"
            "    {'product': row['product'], 'quantity': row['value'] * mo_qty}\n"
            "    for row in t_recipe\n"
            "]",
        )
        order = self._make_order(qty=10.0)
        poc = self._fill(self._make_poc(order))
        self.env["sale.order.poc.line"].create(
            {
                "poc_id": poc.id,
                "param_id": recipe.id,
                "key": "additive",
                "product_id": self.granulate.id,
                "value": 0.3,
            }
        )
        order.action_confirm()
        production = poc.production_ids
        extra = self._raw(production, self.granulate)
        self.assertEqual(len(extra), 1)
        self.assertAlmostEqual(extra.product_uom_qty, 3.0)
        self.assertEqual(extra.bom_line_id, self.line_film)
        # преизчислението по POC пази допълнителния ход
        poc.with_user(self.manager).write(
            {"params": {**(poc.params._values or {}), "t_width_mm": 400.0}}
        )
        self.assertEqual(len(self._raw(production, self.granulate)), 1)
        self.assertAlmostEqual(
            self._raw(production, self.granulate).product_uom_qty, 3.0
        )

    def test_order_without_configuration_is_untouched(self):
        self._formula(self.line_film, "result = t_width_mm * mo_qty")
        production = self.env["mrp.production"].create(
            {"product_id": self.product.id, "product_qty": 10.0, "bom_id": self.bom.id}
        )
        self.assertFalse(production.poc_id)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 20.0)
