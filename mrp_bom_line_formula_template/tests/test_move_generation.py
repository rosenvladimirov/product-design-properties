# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
E2E тестове за собствения evaluation hook в ``mrp.production``:
формулата на BoM линията определя количеството на raw move-а при
създаване на MO (без външния formula-quantity модул).
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestFormulaMoveGeneration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["product.product"].create(
            {"name": "Formula Parent", "is_storable": True}
        )
        cls.component = cls.env["product.product"].create(
            {"name": "Formula Component", "is_storable": True}
        )
        cls.override_component = cls.env["product.product"].create(
            {"name": "Formula Override Component", "is_storable": True}
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.parent.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )
        cls.line = cls.env["mrp.bom.line"].create(
            {
                "bom_id": cls.bom.id,
                "product_id": cls.component.id,
                "product_qty": 1.0,
            }
        )

    def _set_formula(self, formula):
        template = self.env["mrp.bom.line.formula.template"].create(
            {"name": "move-gen %s" % len(formula), "quantity_formula": formula}
        )
        self.line.formula_template_id = template

    def _make_mo(self, qty=2.0):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.parent.id,
                "bom_id": self.bom.id,
                "product_qty": qty,
            }
        )
        return mo

    def test_formula_sets_move_quantity(self):
        """result = product_uom_qty * 3 → move qty = MO qty * 3."""
        self._set_formula("result = product_uom_qty * 3")
        mo = self._make_mo(qty=2.0)
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertEqual(len(move), 1)
        self.assertAlmostEqual(move.product_uom_qty, 6.0)

    def test_legacy_quantity_variable_sets_move_quantity(self):
        """Legacy ``quantity = ...`` синтаксисът също важи за move-а."""
        self._set_formula("quantity = product_uom_qty + 5")
        mo = self._make_mo(qty=2.0)
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertAlmostEqual(move.product_uom_qty, 7.0)

    def test_no_formula_keeps_standard_quantity(self):
        """Без формула — стандартната експлозия (1 × MO qty)."""
        mo = self._make_mo(qty=4.0)
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertAlmostEqual(move.product_uom_qty, 4.0)

    def test_invalid_result_falls_back_to_standard(self):
        """Нечислов резултат → warning + стандартно количество."""
        self._set_formula("result = 'not-a-number'")
        with self.assertLogs(
            "odoo.addons.mrp_bom_line_formula_template.models.mrp_production",
            level="WARNING",
        ):
            mo = self._make_mo(qty=3.0)
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertAlmostEqual(move.product_uom_qty, 3.0)

    def test_product_override_in_move(self):
        """Формула с product override сменя продукта на move-а."""
        self.env["ir.model.data"].create(
            {
                "name": "test_override_component",
                "module": "mrp_bom_line_formula_template",
                "model": "product.product",
                "res_id": self.override_component.id,
            }
        )
        self._set_formula(
            "result = 2\n"
            "product = env.ref("
            "'mrp_bom_line_formula_template.test_override_component')"
        )
        mo = self._make_mo(qty=1.0)
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.override_component
        )
        self.assertEqual(len(move), 1)
        self.assertAlmostEqual(move.product_uom_qty, 2.0)
