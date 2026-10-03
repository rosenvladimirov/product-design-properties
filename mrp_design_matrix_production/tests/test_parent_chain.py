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
"""Child MO намира родителя си и при производство в 2/3 стъпки.

02.10.2026: на 3 стъпки между готовото движение на child-а и суровото на
родителя стоят Store Finished Product и Pick Components. Прекият поглед
``move_dest_ids.raw_material_production_id`` даваше празно и гардът на
матрицата спираше потвърждаването на покупката (PD00014).
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestParentChain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.door = Product.create({"name": "PCH Door", "is_storable": True})
        cls.frame = Product.create({"name": "PCH Frame", "is_storable": True})
        cls.sheet = Product.create({"name": "PCH Sheet", "is_storable": True})
        Bom = cls.env["mrp.bom"]
        cls.door_bom = Bom.create({
            "product_tmpl_id": cls.door.product_tmpl_id.id,
            "bom_line_ids": [(0, 0, {"product_id": cls.frame.id, "product_qty": 1})],
        })
        cls.frame_bom = Bom.create({
            "product_tmpl_id": cls.frame.product_tmpl_id.id,
            "bom_line_ids": [(0, 0, {"product_id": cls.sheet.id, "product_qty": 1})],
        })
        cls.stock = cls.env.ref("stock.stock_location_stock")

    def _mo(self, product, bom):
        return self.env["mrp.production"].create(
            {"product_id": product.id, "bom_id": bom.id, "product_qty": 1}
        )

    def _move(self, dest):
        """Складово движение (Store / Pick), което захранва ``dest``."""
        return self.env["stock.move"].create({
            "product_id": self.frame.id,
            "product_uom_qty": 1,
            "location_id": self.stock.id,
            "location_dest_id": self.stock.id,
            "move_dest_ids": [(4, dest.id)],
        })

    def test_tri_stapki_prez_store_i_pick(self):
        """Готово на child → Store → Pick → сурово на родителя."""
        parent = self._mo(self.door, self.door_bom)
        child = self._mo(self.frame, self.frame_bom)
        raw = parent.move_raw_ids.filtered(lambda m: m.product_id == self.frame)
        pick = self._move(raw)
        store = self._move(pick)
        child.move_finished_ids.move_dest_ids = [(6, 0, store.ids)]
        self.assertEqual(child._design_parent_raw_move(), raw)

    def test_tri_stapki_prez_move_dest_na_mo(self):
        """Връзката от procurement-а (MO.move_dest_ids) също се обхожда."""
        parent = self._mo(self.door, self.door_bom)
        child = self._mo(self.frame, self.frame_bom)
        raw = parent.move_raw_ids.filtered(lambda m: m.product_id == self.frame)
        store = self._move(self._move(raw))
        child.move_dest_ids = [(6, 0, store.ids)]
        self.assertEqual(child._design_parent_raw_move(), raw)

    def test_edna_stapka_pryako(self):
        """1 стъпка: готовото сочи директно суровото — както досега."""
        parent = self._mo(self.door, self.door_bom)
        child = self._mo(self.frame, self.frame_bom)
        raw = parent.move_raw_ids.filtered(lambda m: m.product_id == self.frame)
        child.move_finished_ids.move_dest_ids = [(6, 0, raw.ids)]
        self.assertEqual(child._design_parent_raw_move(), raw)

    def test_bez_roditel(self):
        """Самостоятелно MO няма родител — празно, не грешка."""
        child = self._mo(self.frame, self.frame_bom)
        self.assertFalse(child._design_parent_raw_move())
