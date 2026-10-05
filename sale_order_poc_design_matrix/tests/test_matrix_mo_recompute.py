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
"""Матричното MO не се преразгъва по POC след потвърждаване.

Ход с количеството на матрицата (5) — преразгъването по рецептата би го
върнало на статичното 1 (Солид, 05.10.2026: первази 5,9 → 1,0).
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MatrixPocCommon

_T0 = {
    "nodes": [
        {"id": "in", "type": "inputNode", "name": "Request"},
        {"id": "out", "type": "outputNode", "name": "Response"},
    ],
    "edges": [{"id": "e1", "sourceId": "in", "targetId": "out"}],
}


@tagged("post_install", "-at_install")
class TestMatrixMoRecompute(MatrixPocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.raw = cls.env["product.product"].create(
            {"name": "MMR Raw", "is_storable": True}
        )
        cls.bom.bom_line_ids = [(0, 0, {"product_id": cls.raw.id, "product_qty": 1.0})]

    def _mo(self, matrix=True):
        self.bom.constraint_table = _T0 if matrix else False
        order, poc = self._poc_for_matrix()
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "bom_id": self.bom.id,
                "product_qty": 1.0,
                "poc_id": poc.id,
            }
        )
        # нивото на гарда е избор на вертикала (Солид гърми); тук не се мери
        with patch.object(
            type(mo), "_missing_design_context_level", return_value="warn"
        ):
            mo.action_confirm()
        move = mo.move_raw_ids.filtered(lambda m: m.product_id == self.raw)
        # количеството, което е дал матричният пас
        move.product_uom_qty = 5.0
        return mo, move

    def test_butonat_spira(self):
        mo, move = self._mo()
        self.assertTrue(mo.poc_matrix_driven)
        with self.assertRaises(UserError):
            mo.action_poc_recompute()
        self.assertEqual(move.product_uom_qty, 5.0)

    def test_promyanata_na_poc_ne_pipa_sastava(self):
        mo, move = self._mo()
        mo._poc_refresh()
        self.assertEqual(move.product_uom_qty, 5.0, "съставът е на матрицата")

    def test_bez_matrica_se_preizchislyava(self):
        """Рецепта без матрица — преразгъването по POC остава."""
        mo, move = self._mo(matrix=False)
        self.assertFalse(mo.poc_matrix_driven)
        mo.action_poc_recompute()
        self.assertEqual(move.product_uom_qty, 1.0)
