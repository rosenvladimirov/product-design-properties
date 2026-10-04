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
"""Матричният пас тече преди потвърждаването (ADR mrp-design-matrix/0001).

След потвърждаването процюърмънтът и пикингите вече съществуват за скелета
на рецептата: изключен MTO компонент е родил свой MO, Pick Components носи
заместителя. Ходът е вързан и не се трие. Пасът върху черновата го избягва.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_T0 = {
    "nodes": [
        {"id": "in", "type": "inputNode", "name": "Request"},
        {"id": "out", "type": "outputNode", "name": "Response"},
    ],
    "edges": [{"id": "e1", "sourceId": "in", "targetId": "out"}],
}


@tagged("post_install", "-at_install")
class TestPassBeforeConfirm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        mto = cls.env.ref("stock.route_warehouse0_mto")
        mto.active = True
        manufacture = cls.warehouse.manufacture_pull_id.route_id
        Product = cls.env["product.product"]
        cls.door = Product.create(
            {"name": "PBC Door", "is_storable": True, "tracking": "lot"}
        )
        cls.raw = Product.create({"name": "PBC Raw", "is_storable": True})
        cls.semis = {}
        for key in ("off", "on"):
            semi = Product.create(
                {
                    "name": "PBC Semi %s" % key,
                    "is_storable": True,
                    "route_ids": [(6, 0, [mto.id, manufacture.id])],
                }
            )
            cls.env["mrp.bom"].create(
                {
                    "product_tmpl_id": semi.product_tmpl_id.id,
                    "bom_line_ids": [(0, 0, {"product_id": cls.raw.id, "product_qty": 1})],
                }
            )
            cls.semis[key] = semi
        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "pbc_def",
                "name": "PBC Def",
                "design_params_definition": [
                    {"name": "pbc0000000000001", "type": "char", "string": "kind",
                     "default": "on"},
                ],
            }
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.door.product_tmpl_id.id,
                "constraint_table": _T0,
                "bom_line_ids": [
                    (0, 0, {"product_id": cls.semis["off"].id, "product_qty": 1}),
                    (0, 0, {"product_id": cls.semis["on"].id, "product_qty": 1}),
                ],
            }
        )
        # формулата е изчисляемо поле — пише се след създаването на реда.
        # Без контекст (разгъването на черновата) и двата реда са в скелета,
        # както в истинската рецепта; само пасът с контекста изключва „off“.
        for line in cls.bom.bom_line_ids:
            if line.product_id == cls.semis["off"]:
                line.quantity_formula = (
                    "result = 0 if design_context.get('kind') else 1"
                )
            else:
                line.quantity_formula = "result = 1"

    def _mo(self):
        lot = self.env["stock.lot"].create(
            {
                "product_id": self.door.id,
                "name": "PBC-%s" % self.env["stock.lot"].search_count([]),
                "design_param_definition_id": self.definition.id,
                "design_params": {"pbc0000000000001": "on"},
            }
        )
        return self.env["mrp.production"].create(
            {
                "product_id": self.door.id,
                "bom_id": self.bom.id,
                "product_qty": 1,
                "lot_producing_ids": [(6, 0, lot.ids)],
                "picking_type_id": self.warehouse.manu_type_id.id,
            }
        )

    def _children(self, mo):
        return self.env["mrp.production"].search(
            [("product_id", "in", [s.id for s in self.semis.values()]),
             ("id", "!=", mo.id)]
        )

    def test_izklyucheniyat_mto_ne_razhda_mo(self):
        """Изключеният полуфабрикат не ражда дъщерен MO; включеният — ражда."""
        mo = self._mo()
        mo.action_confirm()
        self.assertEqual(mo.move_raw_ids.product_id, self.semis["on"])
        self.assertEqual(self._children(mo).product_id, self.semis["on"])

    def test_tri_stapki_pick_nosi_smetnatiya_sastav(self):
        """При 3 стъпки Pick Components е за сметнатия състав, не за скелета."""
        self.warehouse.manufacture_steps = "pbm_sam"
        mo = self._mo()
        mo.picking_type_id = self.warehouse.manu_type_id
        mo.action_confirm()
        self.assertEqual(mo.move_raw_ids.product_id, self.semis["on"])
        pick = mo.picking_ids.filtered(
            lambda p: p.picking_type_id == self.warehouse.pbm_type_id
        )
        self.assertTrue(pick, "при 3 стъпки има Pick Components")
        self.assertEqual(pick.move_ids.product_id, self.semis["on"])
