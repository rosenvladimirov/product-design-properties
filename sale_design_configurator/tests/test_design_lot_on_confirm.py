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
"""Партида при потвърждаване на продажбата (``design_lot_on_confirm``).

Търгуваната врата получава номер при продажбата, не при приемането: номерът
идва от поредицата на продукта (буквата) и тръгва по веригата до приемането
от доставчика.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDesignLotOnConfirm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sequence = cls.env["ir.sequence"].create(
            {"name": "DLC Letter", "prefix": "ИД", "padding": 4, "company_id": False}
        )
        cls.partner = cls.env["res.partner"].create({"name": "DLC Customer"})
        cls.vendor = cls.env["res.partner"].create({"name": "DLC Vendor"})
        cls.door = cls._door("DLC Door", "lot")

    @classmethod
    def _door(cls, name, tracking, flag=True):
        return cls.env["product.product"].create(
            {
                "name": name,
                "is_storable": True,
                "tracking": tracking,
                "lot_sequence_id": cls.sequence.id,
                "design_lot_on_confirm": flag,
            }
        )

    def _order(self, product, qty=1.0, **line):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {"product_id": product.id, "product_uom_qty": qty, **line}
                    )
                ],
            }
        )

    def test_confirmation_gives_the_line_its_lot(self):
        order = self._order(self.door, qty=3.0)
        order.action_confirm()
        lot = order.order_line.design_lot_id
        self.assertEqual(lot.product_id, self.door)
        self.assertTrue(lot.name.startswith("ИД"), lot.name)
        self.assertEqual(lot.design_state, "sales_confirmed")

    def test_without_the_flag_nothing_is_created(self):
        """Плоскостите и обковът са партидни, но партида при продажба нямат."""
        board = self._door("DLC Board", "lot", flag=False)
        order = self._order(board)
        order.action_confirm()
        self.assertFalse(order.order_line.design_lot_id)

    def test_a_design_lot_on_the_line_is_kept(self):
        own = self.env["stock.lot"].create(
            {"name": "DLC-OWN", "product_id": self.door.id}
        )
        order = self._order(self.door, design_lot_id=own.id)
        order.action_confirm()
        self.assertEqual(order.order_line.design_lot_id, own)

    def test_serial_needs_one_unit_per_line(self):
        door = self._door("DLC Serial Door", "serial")
        with self.assertRaises(UserError):
            self._order(door, qty=2.0).action_confirm()
        order = self._order(door, qty=1.0)
        order.action_confirm()
        self.assertTrue(order.order_line.design_lot_id)

    def test_the_lot_reaches_the_purchase_receipt(self):
        """Поръчка към доставчика: приемането взема партидата от продажбата."""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        route_mto = warehouse.mto_pull_id.route_id
        route_mto.active = True
        self.door.write(
            {
                "route_ids": [
                    Command.set((route_mto | warehouse.buy_pull_id.route_id).ids)
                ],
                "seller_ids": [Command.create({"partner_id": self.vendor.id})],
            }
        )
        order = self._order(self.door, qty=2.0)
        order.action_confirm()
        lot = order.order_line.design_lot_id
        # без партида сравненията долу биха били празно срещу празно
        self.assertTrue(lot)
        po_line = self.env["purchase.order.line"].search(
            [("product_id", "=", self.door.id)]
        )
        self.assertEqual(po_line.design_lot_id, lot)
        po_line.order_id.button_confirm()
        receipt = po_line.order_id.picking_ids
        receipt.action_assign()
        self.assertEqual(receipt.move_ids.move_line_ids.lot_id, lot)
        self.assertAlmostEqual(receipt.move_ids.quantity, 2.0)
