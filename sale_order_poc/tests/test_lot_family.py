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
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestLotFamily(PocCommon):
    """Доставката резервира само от семейството лотове на своя POC."""

    def _confirmed(self, qty=100.0):
        order = self._make_order(qty=qty)
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        return order, poc

    def _stock(self, lot, qty):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock_location, qty, lot_id=lot
        )

    def _picking(self, order):
        return order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))

    def test_delivery_reserves_its_own_lot(self):
        """Два POC с един продукт: всяка доставка взема своя лот.

        Наличността на чуждия лот е създадена първа — без филтъра по
        семейство ядрото по FIFO би резервирало нея (мутацията пада).
        """
        order_a, poc_a = self._confirmed()
        order_b, poc_b = self._confirmed()
        self._stock(poc_b.lot_id, 100.0)
        self._stock(poc_a.lot_id, 100.0)
        picking_a = self._picking(order_a)
        picking_a.action_assign()
        self.assertEqual(picking_a.move_ids.move_line_ids.lot_id, poc_a.lot_id)
        self.assertAlmostEqual(picking_a.move_ids.quantity, 100.0)
        picking_b = self._picking(order_b)
        picking_b.action_assign()
        self.assertEqual(picking_b.move_ids.move_line_ids.lot_id, poc_b.lot_id)

    def test_foreign_stock_only_is_not_reserved(self):
        """Само чужд лот на склад: доставката не резервира нищо."""
        order_a, _poc_a = self._confirmed()
        _order_b, poc_b = self._confirmed()
        self._stock(poc_b.lot_id, 100.0)
        picking_a = self._picking(order_a)
        picking_a.action_assign()
        self.assertFalse(picking_a.move_ids.move_line_ids)
        self.assertAlmostEqual(
            picking_a.move_ids._get_available_quantity(self.stock_location), 0.0
        )

    def test_delivery_takes_all_batches(self):
        """Семейство от две партиди: доставката взема и двете."""
        order, poc = self._confirmed(qty=100.0)
        batch_2 = poc._poc_lot(self.product, new_batch=True)
        self.assertEqual(batch_2.poc_batch, 2)
        self._stock(poc.lot_id, 60.0)
        self._stock(batch_2, 40.0)
        picking = self._picking(order)
        picking.action_assign()
        self.assertEqual(
            picking.move_ids.move_line_ids.lot_id, poc.lot_id | batch_2
        )
        self.assertAlmostEqual(picking.move_ids.quantity, 100.0)

    def test_done_with_foreign_lot_is_refused(self):
        order_a, poc_a = self._confirmed()
        _order_b, poc_b = self._confirmed()
        self._stock(poc_a.lot_id, 100.0)
        self._stock(poc_b.lot_id, 100.0)
        picking = self._picking(order_a)
        picking.action_assign()
        picking.move_ids.move_line_ids.lot_id = poc_b.lot_id
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_two_configurations_do_not_merge_moves(self):
        """Два реда с един продукт в една поръчка: две движения, не едно."""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 10.0}),
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 20.0}),
                ],
            }
        )
        for line in order.order_line:
            self._fill(self.env["sale.order.poc"].create({"sale_line_id": line.id}))
        order.action_confirm()
        moves = self._picking(order).move_ids
        self.assertEqual(len(moves), 2)
        self.assertEqual(len(moves.poc_id), 2)
