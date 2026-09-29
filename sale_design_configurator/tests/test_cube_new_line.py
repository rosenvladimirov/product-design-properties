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
"""Кубчето на нов ред записва офертата, преди да роди партида — в браузъра.

Солид, 29.09 (Атанас, msg 167826): търговка натиска кубчето на ред в
незаписана оферта; партидата се ражда, а секунда по-късно onchange на реда
без поръчката пада с „Expected singleton: sale.order()“ и партидата остава
без ред. Сървърът не го вижда — пътят е през уиджета.
"""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestCubeNewLine(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        definition = cls.env["design.param.definition"].create(
            {
                "code": "test_cube_new_line",
                "name": "Test Cube New Line",
                "design_params_definition": [
                    {
                        "name": "c0be000000000001",
                        "type": "float",
                        "string": "Width",
                        "default": 900.0,
                    },
                ],
            }
        )
        sequence = cls.env["ir.sequence"].create(
            {"name": "DLC Cube", "prefix": "DLC-CUBE-", "padding": 3}
        )
        cls.door = cls.env["product.product"].create(
            {
                "name": "DLC Cube Door",
                "is_storable": True,
                "tracking": "lot",
                "sale_ok": True,
                "lot_sequence_id": sequence.id,
                "design_param_definition_id": definition.id,
            }
        )
        partner = cls.env["res.partner"].create({"name": "DLC Cube Customer"})
        cls.order = cls.env["sale.order"].create({"partner_id": partner.id})

    def test_cube_on_a_new_line_saves_the_order_first(self):
        self.start_tour(
            f"/odoo/action-sale.action_quotations_with_onboarding/{self.order.id}",
            "sale_design_configurator_cube_new_line",
            login="admin",
        )
        line = self.order.order_line
        self.assertEqual(len(line), 1, "the new line was not saved")
        self.assertEqual(line.product_id, self.door)
        self.assertTrue(line.design_lot_id.name.startswith("DLC-CUBE-"))
        self.assertEqual(line.design_lot_id.product_id, self.door)
        # една партида — нищо висящо от прекъснат опит
        self.assertEqual(
            self.env["stock.lot"].search_count([("product_id", "=", self.door.id)]), 1
        )
