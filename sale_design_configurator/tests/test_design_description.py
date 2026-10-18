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
"""Описанието на реда от параметрите на дизайн партидата (порт от 18.0).

В 18.0 смяната на партидата преписваше описанието на реда с името на
продукта и списък „етикет: стойност“, скривайки сентинела ``use_main`` и
цветовете, равни на основния. В 19.0 същото важи само за чернова/изпратена
оферта: на потвърдена поръчка партидата се връзва системно (партида при
продажба, POC) и описанието не бива да се мени.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MODEL_UUID = "a1b2c3d4e5f60718"
MAIN_UUID = "b2c3d4e5f6071829"
BOX_UUID = "c3d4e5f60718293a"
SLAT_UUID = "d4e5f60718293a4b"


@tagged("post_install", "-at_install")
class TestDesignDescription(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = cls.env["design.param.definition"].create({
            "code": "test_design_description",
            "name": "Test Design Description",
            "design_params_definition": [
                {"name": MODEL_UUID, "type": "selection", "string": "shutter_model",
                 "selection": [["std", "Standard"], ["thermo", "Thermo Comfort"]]},
                {"name": MAIN_UUID, "type": "char", "string": "main_color"},
                {"name": BOX_UUID, "type": "char", "string": "color_box"},
                {"name": SLAT_UUID, "type": "char", "string": "color_slat"},
            ],
        })
        cls.product = cls.env["product.product"].create({
            "name": "Description Shutter",
            "is_storable": True,
            "tracking": "lot",
            "design_param_definition_id": cls.definition.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Description Customer"})

    def _lot(self, params):
        return self.env["stock.lot"].create({
            "name": "DESC-%s" % len(params),
            "product_id": self.product.id,
            "design_param_definition_id": self.definition.id,
            "design_params": params,
        })

    def _line(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id,
                                   "product_uom_qty": 1.0})],
        })
        return order.order_line

    def test_bullets_hide_sentinel_and_main_color_copies(self):
        lot = self._lot({MODEL_UUID: "thermo", MAIN_UUID: "RAL9016",
                         BOX_UUID: "RAL9016", SLAT_UUID: "use_main"})
        line = self._line()
        line.design_lot_id = lot
        self.assertEqual(line._build_design_param_bullets(),
                         ["shutter_model: Thermo Comfort", "main_color: RAL9016"])

    def test_set_design_lot_rewrites_draft_description(self):
        lot = self._lot({MODEL_UUID: "std", MAIN_UUID: "RAL7016",
                         BOX_UUID: "RAL9016"})
        line = self._line()
        line.set_design_lot(lot.id)
        self.assertEqual(line.name, "\n".join([
            self.product.display_name,
            "• shutter_model: Standard",
            "• main_color: RAL7016",
            "• color_box: RAL9016",
        ]))

    def test_confirmed_order_keeps_its_description(self):
        lot = self._lot({MODEL_UUID: "std", MAIN_UUID: "RAL7016"})
        line = self._line()
        line.order_id.action_confirm()
        before = line.name
        line.design_lot_id = lot
        self.assertEqual(line.name, before)

    def test_empty_lot_does_not_touch_description(self):
        line = self._line()
        before = line.name
        line.design_lot_id = self._lot({})
        self.assertEqual(line.name, before)
