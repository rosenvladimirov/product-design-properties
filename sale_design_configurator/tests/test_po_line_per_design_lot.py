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
"""Всяка дизайн партида получава свой ред в покупката.

Ядрото слива процюърмънти за един продукт в един ред на черновата покупка.
Вторият ред се добавя към вече потвърдена поръчка, за да мине през
търсенето на кандидат (урокът от test_mo_per_design_lot).
"""

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPoLinePerDesignLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env.ref("stock.warehouse0")
        route_mto = warehouse.mto_pull_id.route_id
        route_mto.active = True
        route_buy = cls.env.ref("purchase_stock.route_warehouse0_buy")
        vendor = cls.env["res.partner"].create({"name": "PLD Vendor"})
        cls.door = cls.env["product.product"].create(
            {
                "name": "PLD Door",
                "is_storable": True,
                "tracking": "lot",
                "route_ids": [Command.set((route_mto | route_buy).ids)],
                "seller_ids": [Command.create({"partner_id": vendor.id})],
            }
        )
        Lot = cls.env["stock.lot"]
        cls.lot_a = Lot.create({"name": "PLD-A", "product_id": cls.door.id})
        cls.lot_b = Lot.create({"name": "PLD-B", "product_id": cls.door.id})
        cls.partner = cls.env["res.partner"].create({"name": "PLD Customer"})

    def _line(self, lot, qty=1.0):
        return Command.create(
            {
                "product_id": self.door.id,
                "product_uom_qty": qty,
                "design_lot_id": lot.id,
            }
        )

    def _po_lines(self):
        return self.env["purchase.order.line"].search(
            [("product_id", "=", self.door.id)]
        )

    def test_vsyaka_partida_e_svoy_red(self):
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [self._line(self.lot_a)]}
        )
        order.action_confirm()
        order.write({"order_line": [self._line(self.lot_b)]})
        lines = self._po_lines()
        self.assertEqual(len(lines.order_id), 1, "една чернова покупка")
        self.assertEqual(
            {line.design_lot_id: line.product_qty for line in lines},
            {self.lot_a: 1.0, self.lot_b: 1.0},
            "двете врати станаха един ред",
        )

    def test_sashtata_partida_ostava_v_reda_si(self):
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [self._line(self.lot_a)]}
        )
        order.action_confirm()
        order.write({"order_line": [self._line(self.lot_a)]})
        lines = self._po_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.product_qty, 2.0)
