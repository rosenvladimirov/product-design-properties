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
"""Една бройка — един ред — една дизайн партида (Солид, 05.10.2026, т. 15).

Атанас на SD00039: новият ред беше без конфигурация, количеството на реда
не разделяше, а след потвърждаване две врати оставаха на една партида и
покупката ставаше един ред за 3 бр.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sale_order_poc_design_matrix.tests.common import MatrixPocCommon


@tagged("post_install", "-at_install")
class TestOneUnitPerLine(MatrixPocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.poc_one_unit_per_line = True

    def _configured_order(self, width=300.0):
        order = self._make_order(qty=1.0)
        poc = self._fill(self._make_poc(order), width=width)
        return order, poc

    def _width(self, line):
        return line.poc_id._poc_values()["t_width_mm"]

    def test_chernova_kopira_konfiguraciyata(self):
        """Количество 3 на реда: три реда по 1, всеки със свое копие на POC."""
        order, poc = self._configured_order(width=410.0)
        order.order_line.product_uom_qty = 3
        lines = order.order_line
        self.assertEqual(lines.mapped("product_uom_qty"), [1.0, 1.0, 1.0])
        self.assertEqual(len(lines.poc_id), 3, "всеки ред — своя конфигурация")
        self.assertEqual([self._width(line) for line in lines], [410.0] * 3)
        # копието се мени поотделно
        lines[1].poc_id._poc_set_params({"t_width_mm": 500.0})
        self.assertEqual([self._width(line) for line in lines], [410.0, 500.0, 410.0])

    def test_nov_red_s_kolichestvo_se_razdelya(self):
        order = self._make_order(qty=2.0)
        self.assertEqual(order.order_line.mapped("product_uom_qty"), [1.0, 1.0])

    def test_bez_otmetkata_ne_se_razdelya(self):
        """Торбите на Пакит: един POC за хиляди бройки остава един ред."""
        self.product.poc_one_unit_per_line = False
        order, poc = self._configured_order()
        order.order_line.product_uom_qty = 1000
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_uom_qty, 1000.0)

    def test_drobno_kolichestvo_e_greshka(self):
        order, poc = self._configured_order()
        with self.assertRaises(UserError):
            order.order_line.product_uom_qty = 2.5

    def test_ogledalniyat_red_ne_se_razdelya(self):
        """Ред с чужда конфигурация през партидата следва покупката."""
        order, poc = self._configured_order()
        lot = self.env["stock.lot"].create(
            {"product_id": self.product.id, "name": "MIRROR-1", "poc_id": poc.id}
        )
        mirror = self._make_order(qty=1.0)
        mirror.order_line.design_lot_id = lot
        mirror.order_line.product_uom_qty = 2
        self.assertEqual(len(mirror.order_line), 1)
        self.assertEqual(mirror.order_line.product_uom_qty, 2.0)


@tagged("post_install", "-at_install")
class TestOneUnitPerLineConfirmed(MatrixPocCommon):
    """След потвърждаване: следваща партида и свой ред в покупката."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        route_mto = cls.warehouse.mto_pull_id.route_id
        route_mto.active = True
        route_buy = cls.env.ref("purchase_stock.route_warehouse0_buy")
        vendor = cls.env["res.partner"].create({"name": "OUL Vendor"})
        cls.product.write(
            {
                "poc_one_unit_per_line": True,
                "design_lot_on_confirm": True,
                "route_ids": [Command.set((route_mto | route_buy).ids)],
                "seller_ids": [Command.create({"partner_id": vendor.id})],
            }
        )

    def test_sled_potvarzhdane_sledvashta_partida(self):
        order = self._make_order(qty=1.0)
        poc = self._fill(self._make_poc(order), width=410.0)
        order.action_confirm()
        first = order.order_line
        lot_a = first.design_lot_id
        self.assertTrue(lot_a, "потвърждаването дава дизайн партида")

        first.product_uom_qty = 2
        self.assertEqual(first.product_uom_qty, 1.0, "редът остава с една врата")
        second = order.order_line - first
        self.assertEqual(second.product_uom_qty, 1.0)
        self.assertTrue(second.poc_id, "новият ред носи конфигурацията")
        self.assertNotEqual(second.poc_id, poc)
        self.assertEqual(self._width_of(second), 410.0)
        lot_b = second.design_lot_id
        self.assertTrue(lot_b)
        self.assertNotEqual(lot_b, lot_a, "втората врата — своя партида")
        self.assertEqual(second.poc_id.lot_id, lot_b, "POC осиновява партидата си")

        po_lines = self.env["purchase.order.line"].search(
            [("product_id", "=", self.product.id)]
        )
        self.assertEqual(
            {line.design_lot_id: line.product_qty for line in po_lines},
            {lot_a: 1.0, lot_b: 1.0},
            "всяка партида — свой ред в покупката",
        )

    def _width_of(self, line):
        return line.poc_id._poc_values()["t_width_mm"]
