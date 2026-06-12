# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
"""
E2E тестове: формулата контролира кои forced лотове (и колко от лот)
консумира raw move-ът на MO-то.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestFormulaForcedLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["product.product"].create(
            {"name": "FL Parent", "is_storable": True}
        )
        cls.component = cls.env["product.product"].create(
            {
                "name": "FL Component",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.lot_a = cls.env["stock.lot"].create(
            {"name": "FL-LOT-A", "product_id": cls.component.id}
        )
        cls.lot_b = cls.env["stock.lot"].create(
            {"name": "FL-LOT-B", "product_id": cls.component.id}
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
                "product_qty": 4.0,
            }
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_loc = cls.warehouse.lot_stock_id

    def _set_formula(self, formula):
        template = self.env["mrp.bom.line.formula.template"].create(
            {"name": "fl %s" % len(formula), "quantity_formula": formula}
        )
        self.line.formula_template_id = template

    def _add_stock(self, lot, qty):
        self.env["stock.quant"]._update_available_quantity(
            self.component, self.stock_loc, qty, lot_id=lot
        )

    def _make_mo(self, qty=1.0):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.parent.id,
                "bom_id": self.bom.id,
                "product_qty": qty,
            }
        )
        mo.action_confirm()
        return mo

    def test_forced_lots_from_formula(self):
        """forced_lots = recordset → forced_lot_ids на raw move-а."""
        self._set_formula(
            "result = 4\n"
            "forced_lots = lot_model.search("
            "[('name', '=', 'FL-LOT-A'), ('product_id', '=', product.id)])"
        )
        mo = self._make_mo()
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertEqual(move.forced_lot_ids, self.lot_a)

    def test_no_forced_lots_without_output(self):
        """Без forced_lots изход — move без форсирани лотове."""
        self._set_formula("result = 4")
        mo = self._make_mo()
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertFalse(move.forced_lot_ids)

    def test_per_lot_quantities(self):
        """forced_lots = {lot: qty} → точни количества по лотове след
        резервация (вместо pro-rata)."""
        self._add_stock(self.lot_a, 10.0)
        self._add_stock(self.lot_b, 10.0)
        self._set_formula(
            "result = 4\n"
            "la = lot_model.search([('name', '=', 'FL-LOT-A'), "
            "('product_id', '=', product.id)])\n"
            "lb = lot_model.search([('name', '=', 'FL-LOT-B'), "
            "('product_id', '=', product.id)])\n"
            "forced_lots = {la: 3.0, lb: 1.0}"
        )
        mo = self._make_mo()
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertEqual(
            set(move.forced_lot_ids.ids), {self.lot_a.id, self.lot_b.id}
        )
        self.assertEqual(
            (move.forced_lot_extra_data or {}).get("formula_lot_qty"),
            {str(self.lot_a.id): 3.0, str(self.lot_b.id): 1.0},
        )
        mo.action_assign()
        qty_by_lot = {
            line.lot_id: line.quantity
            for line in move.move_line_ids
            if line.lot_id
        }
        self.assertAlmostEqual(qty_by_lot.get(self.lot_a, 0.0), 3.0)
        self.assertAlmostEqual(qty_by_lot.get(self.lot_b, 0.0), 1.0)

    def test_mo_forced_lots_in_context(self):
        """mo_forced_lots е наличен в контекста (от move-ове на MO-то)."""
        self._set_formula(
            "result = 4\n"
            "forced_lots = lot_model.search("
            "[('name', '=', 'FL-LOT-B'), ('product_id', '=', product.id)])"
        )
        mo = self._make_mo()
        # MO-level forced_lot_ids е computed от move-овете
        self.assertIn(self.lot_b, mo.forced_lot_ids)
