# Copyright 2026 Rosen Vladimirov, Terraros Commerce Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Всяка дизайн партида получава свое MO, и при по-късно снабдяване.

Ядрото търси съществуващо MO по продукт, рецепта и референцията на
поръчката. Два реда, потвърдени НАВЕДНЪЖ, не минават през търсенето — затова
вторият ред се добавя към вече потвърдена поръчка (урокът от
sale_order_poc_mrp: иначе мутацията дава фалшиво зелено).
"""

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMoPerDesignLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env.ref("stock.warehouse0")
        route_mto = warehouse.mto_pull_id.route_id
        route_mto.active = True
        route_manufacture = warehouse.manufacture_pull_id.route_id
        Product = cls.env["product.product"]
        cls.door = Product.create(
            {
                "name": "MPD Door",
                "is_storable": True,
                "tracking": "lot",
                "route_ids": [Command.set((route_mto | route_manufacture).ids)],
            }
        )
        cls.board = Product.create({"name": "MPD Board", "is_storable": True})
        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.door.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create({"product_id": cls.board.id, "product_qty": 2.0})
                ],
            }
        )
        Lot = cls.env["stock.lot"]
        cls.lot_a = Lot.create({"name": "MPD-A", "product_id": cls.door.id})
        cls.lot_b = Lot.create({"name": "MPD-B", "product_id": cls.door.id})
        cls.partner = cls.env["res.partner"].create({"name": "MPD Customer"})

    def _line(self, lot, qty):
        return Command.create(
            {
                "product_id": self.door.id,
                "product_uom_qty": qty,
                "design_lot_id": lot.id,
            }
        )

    def _productions(self):
        return self.env["mrp.production"].search([("product_id", "=", self.door.id)])

    def test_later_line_gets_its_own_order(self):
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [self._line(self.lot_a, 1.0)]}
        )
        order.action_confirm()
        self.assertEqual(len(self._productions()), 1)
        order.write({"order_line": [self._line(self.lot_b, 2.0)]})
        productions = self._productions()
        self.assertEqual(
            len(productions), 2, "the second door went into the first order"
        )
        by_lot = {p.design_lot_id: p for p in productions}
        self.assertEqual(by_lot[self.lot_a].product_qty, 1.0)
        self.assertEqual(by_lot[self.lot_b].product_qty, 2.0)
        self.assertEqual(by_lot[self.lot_b].lot_producing_ids, self.lot_b)

    def _grow(self, lot):
        """Поръчка с една врата, потвърдена, после вратите стават три.

        Връща MO-тата на поръчката (по референцията ѝ — чужди поръчки не влизат).
        """
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [self._line(lot, 1.0)]}
        )
        order.action_confirm()
        order.order_line.product_uom_qty = 3.0
        return self.env["mrp.production"].search(
            [
                ("product_id", "=", self.door.id),
                ("reference_ids", "in", order.stock_reference_ids.ids),
            ]
        )

    def test_more_of_the_same_lot_stays_in_its_order(self):
        """Същата партида, повече бройки — остава при своята партида.

        Дали добавката влиза в ПОТВЪРДЕНОТО MO, решава стекът, не тази
        партида: ядрото слива в draft и confirmed, а клиентски модул може да
        замрази confirmed (Теолино, ``teolino_mrp_freeze_confirmed`` — сливане
        само в draft, ново търсене ражда ново MO). Затова сравняваме с контрола
        без партида в същия стек: терминът на партидата не бива да променя
        сливането за същата партида. Различните партиди — в
        ``test_later_line_gets_its_own_order``.
        """
        control = self._grow(self.env["stock.lot"])
        productions = self._grow(self.lot_a)
        self.assertEqual(
            len(productions),
            len(control),
            "the design lot changed how more of the same is merged",
        )
        self.assertEqual(productions.design_lot_id, self.lot_a)
        self.assertEqual(productions.lot_producing_ids, self.lot_a)
        self.assertEqual(sum(productions.mapped("product_qty")), 3.0)
        if len(control) == 1:
            # стекът слива в потвърденото MO — ядрото
            self.assertEqual(productions.product_qty, 3.0)
