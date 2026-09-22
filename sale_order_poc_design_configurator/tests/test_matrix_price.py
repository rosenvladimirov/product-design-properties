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
"""Цената на офертата от матрицата (ADR sale-order-poc/0019).

На черновата партида не се ражда: матрицата разгъва рецептата на сухо,
стандартната калкулация на Odoo я цени, машината за референтна цена
превръща себестойността в цена — и тя отива в POC и в реда.

Подменен е само сухият пробег на матрицата (редове и операции за дадено
количество) — аритметиката му я пазят тестовете на ``mrp_design_matrix_cost``.
Калкулацията по рецептата и референтната цена тук са истинските.
"""

from unittest import SkipTest
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.sale_order_poc_design_matrix.tests.common import MatrixPocCommon


@tagged("post_install", "-at_install")
class TestMatrixPrice(MatrixPocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "reference_pricelist_id" not in cls.env["res.company"]._fields:
            # мостът не зависи от машината (OPL-1); без нея няма какво да се мери
            raise SkipTest("product_reference_price is not installed")
        cls.sheet = cls.env["product.product"].create(
            {"name": "Test Sheet", "is_storable": True, "standard_price": 2.0}
        )
        cls.workcenter = cls.env["mrp.workcenter"].create(
            {"name": "Test Slotter", "code": "TSLOT", "costs_hour": 30.0}
        )
        # референтната листа: себестойност × 2
        cls.ref_pricelist = cls.env["product.pricelist"].create(
            {"name": "Test reference (cost × 2)"}
        )
        cls.env["product.pricelist.item"].create(
            {
                "pricelist_id": cls.ref_pricelist.id,
                "applied_on": "3_global",
                "base": "standard_price",
                "compute_price": "percentage",
                "percent_price": -100.0,
            }
        )
        cls.env.company.reference_pricelist_id = cls.ref_pricelist
        cls.calls = []

    def _dry_run(self, result=None):
        """Сухият пробег: 0,5 лист на брой и 60 минути на поръчката."""

        def fake(
            bom, design_context=None, product_uom_qty=1.0, sale_record=None, _depth=0
        ):
            self.calls.append((dict(design_context or {}), product_uom_qty))
            if result is not None:
                return result
            return {
                "lines": [
                    {
                        "product_id": self.sheet.id,
                        "qty": 0.5 * product_uom_qty,
                        "uom_id": self.sheet.uom_id.id,
                    }
                ],
                "operations": [
                    {
                        "name": "Slot",
                        "workcenter_id": self.workcenter.id,
                        "minutes": 60.0,
                    }
                ],
            }

        return patch.object(
            type(self.env["mrp.bom"]),
            "simulate_design_cost",
            autospec=True,
            side_effect=fake,
        )

    def _order(self, qty=100.0, uom=None):
        with self._dry_run():
            order = self._make_order(qty=qty)
            if uom:
                order.order_line.product_uom_id = uom
            poc = self._fill(self._make_poc(order))
            poc._poc_set_params({"t_board": self.board.id})
            poc._poc_compute_derived()
        return order, order.order_line, poc

    def test_price_is_the_bom_cost_through_the_reference(self):
        _order, line, poc = self._order(qty=100.0)
        # рецептата за 100: 50 листа × 2,00 + 1 ч × 30,00 = 130,00 ⇒ 1,30 брой
        self.assertAlmostEqual(poc.matrix_cost_unit, 1.30, places=4)
        # референтната листа: × 2
        self.assertAlmostEqual(poc.matrix_price_unit, 2.60, places=4)
        self.assertAlmostEqual(line.price_unit, 2.60, places=4)
        context, qty = self.calls[-1]
        # матрицата получава контекста на POC, за цялото количество
        self.assertEqual((context["t_width_mm"], qty), (300.0, 100.0))
        self.assertEqual(context["t_trim_waste"], 0.05)
        self.assertNotIn("t_thickness_um", context)

    def test_dry_run_leaves_no_trace(self):
        boms = self.env["mrp.bom"].search_count([])
        lots = self.env["stock.lot"].search_count([])
        self._order()
        self.assertEqual(self.env["mrp.bom"].search_count([]), boms)
        self.assertEqual(self.env["stock.lot"].search_count([]), lots)
        self.assertEqual(self.product.standard_price, 0.0)

    def test_quantity_change_reprices_the_draft(self):
        _order, line, _poc = self._order(qty=100.0)
        with self._dry_run():
            line.product_uom_qty = 200.0
        # 100 листа × 2,00 + 30,00 = 230,00 ⇒ 1,15 ⇒ × 2 = 2,30
        self.assertAlmostEqual(line.price_unit, 2.30, places=4)

    def test_line_in_packs_is_priced_per_pack(self):
        pack = self.env["uom.uom"].create(
            {
                "name": "Test Pack of 10",
                "relative_factor": 10.0,
                "relative_uom_id": self.product.uom_id.id,
            }
        )
        self.product.product_tmpl_id.uom_ids = [(4, pack.id)]
        _order, line, _poc = self._order(qty=10.0, uom=pack)
        # 10 пакета = 100 броя ⇒ 2,60 брой ⇒ 26,00 пакет
        self.assertEqual(self.calls[-1][1], 100.0)
        self.assertAlmostEqual(line.price_unit, 26.0, places=4)

    def test_price_set_by_hand_is_kept(self):
        _order, line, poc = self._order(qty=100.0)
        line.price_unit = 15.0
        with self._dry_run():
            poc._poc_set_params({"t_width_mm": 700.0})
            poc._poc_compute_derived()
        self.assertEqual(line.price_unit, 15.0)
        self.assertAlmostEqual(poc.matrix_price_unit, 2.60, places=4)

    def test_matrix_error_leaves_the_line(self):
        with self._dry_run({"error": "T0: bag too long"}):
            order = self._make_order(qty=100.0)
            poc = self._fill(self._make_poc(order))
        self.assertEqual(order.order_line.price_unit, 1.0)
        self.assertFalse(poc.matrix_price_unit)
        self.assertEqual(poc.matrix_price_note, "T0: bag too long")

    def test_no_reference_rule_leaves_the_line(self):
        self.env.company.reference_pricelist_id = False
        _order, line, poc = self._order(qty=100.0)
        self.assertEqual(line.price_unit, 1.0)
        self.assertAlmostEqual(poc.matrix_cost_unit, 1.30, places=4)
        self.assertIn("No reference pricelist", poc.matrix_price_note)

    def test_the_confirmed_order_is_not_repriced(self):
        order, line, poc = self._order(qty=100.0)
        with self._dry_run():
            order.action_confirm()
            calls = len(self.calls)
            poc._poc_compute_derived()
        self.assertEqual(len(self.calls), calls)
        self.assertAlmostEqual(line.price_unit, 2.60, places=4)

    def test_no_lot_on_the_draft(self):
        _order, line, poc = self._order()
        self.assertFalse(poc.lot_id)
        self.assertFalse(line.design_lot_id)
