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
"""MO-level design config: dual-read, copy на split/backorder, merge политика,
контрол на партидата + отпечатък. End-to-end T2 populate се покрива от PCB
вертикала с реален ZenRunner темплейт (hand-built JDM не се оценява надеждно
в unit контекст под текущата zen версия)."""
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMoConfig(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.BomLine = cls.env["mrp.bom.line"]
        cls.Production = cls.env["mrp.production"]
        cls.Lot = cls.env["stock.lot"]
        cls.Definition = cls.env["design.param.definition"]

        # Финалният продукт е НЕ lot-tracked — целта: конфигът живее на MO-то,
        # затова матрицата работи БЕЗ произвеждана партида.
        cls.finished = cls.Product.create(
            {"name": "MOC Door", "is_storable": True, "tracking": "none"}
        )
        cls.finished_lot = cls.Product.create(
            {"name": "MOC Door Lot", "is_storable": True, "tracking": "lot"}
        )
        cls.slab = cls.Product.create({"name": "MOC Slab", "is_storable": True})
        cls.glass = cls.Product.create({"name": "MOC Glass", "is_storable": True})

        cls.definition = cls.Definition.create(
            {
                "code": "moc_def",
                "name": "MOC Def",
                "design_params_definition": [
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "default": "wood",
                        "selection": [["wood", "Wood"], ["glass", "Glass"]],
                    },
                ],
            }
        )

    def _build_bom(self, product=None, **tables):
        lines = tables.pop("lines", None)
        bom = self.Bom.create(
            {
                "product_tmpl_id": (product or self.finished).product_tmpl_id.id,
                "product_qty": 1.0,
                "design_param_definition_id": self.definition.id,
                **tables,
            }
        )
        for line_vals in lines or []:
            self.BomLine.create({"bom_id": bom.id, **line_vals})
        return bom

    def _mo(self, bom, product=None, design_params=None, lot=None):
        vals = {
            "product_id": (product or self.finished).id,
            "product_qty": 1.0,
            "product_uom_id": (product or self.finished).uom_id.id,
            "bom_id": bom.id,
        }
        if design_params is not None:
            vals["design_param_definition_id"] = self.definition.id
            vals["design_params"] = design_params
        if lot is not None:
            vals["lot_producing_ids"] = [(4, lot.id)]
        return self.Production.create(vals)

    def _lot(self, product, **params):
        serial = self.env["ir.sequence"].next_by_code("stock.lot.serial") or "X"
        return self.Lot.create(
            {
                "name": f"MOC-LOT-{serial}",
                "product_id": product.id,
                "design_param_definition_id": self.definition.id,
                "design_params": params or False,
            }
        )

    # ── Dual-read ────────────────────────────────────────────────────────
    def test_mo_config_context_no_lot(self):
        """_resolve_design_context чете от MO-то БЕЗ произвеждана партида."""
        bom = self._build_bom()
        mo = self._mo(bom, design_params={"material": "glass"})
        self.assertFalse(mo.lot_producing_ids)
        ctx = mo._resolve_design_context()
        self.assertIsNotNone(ctx)
        # ключът е string_name на параметъра (както резолверът винаги е правил)
        self.assertIn("glass", ctx.values())

    def test_lot_fallback_when_no_mo_config(self):
        """Без MO конфиг → fallback към произвежданата партида (заварени
        вертикали)."""
        bom = self._build_bom(product=self.finished_lot)
        lot = self._lot(self.finished_lot, material="wood")
        mo = self._mo(bom, product=self.finished_lot, lot=lot)
        self.assertFalse(mo.design_param_definition_id)
        ctx = mo._resolve_design_context()
        self.assertIn("wood", ctx.values())

    def test_mo_and_lot_context_identical(self):
        """Dual-read инвариант: MO конфиг и партида с СЪЩИТЕ параметри дават
        ИДЕНТИЧЕН design context → engine-ът се държи еднакво независимо от
        източника (end-to-end populate се покрива от PCB вертикала с реален
        ZenRunner темплейт)."""
        bom = self._build_bom(product=self.finished_lot)
        lot = self._lot(self.finished_lot, material="glass")
        mo_lot = self._mo(bom, product=self.finished_lot, lot=lot)
        mo_cfg = self._mo(
            bom, product=self.finished_lot, design_params={"material": "glass"}
        )
        self.assertEqual(
            mo_lot._resolve_design_context(),
            mo_cfg._resolve_design_context(),
        )

    # ── Split / backorder пропагация (copy=True) ─────────────────────────
    def test_config_travels_on_copy(self):
        """copy() пренася конфига → split/backorder (core ползва copy_data)."""
        bom = self._build_bom()
        mo = self._mo(bom, design_params={"material": "glass"})
        clone = mo.copy()
        self.assertEqual(
            clone.design_param_definition_id, mo.design_param_definition_id
        )
        self.assertEqual(
            clone.design_params.get("material"),
            mo.design_params.get("material"),
        )

    def test_copy_data_includes_config(self):
        """copy_data (използван от _split_productions) носи конфиг полетата."""
        bom = self._build_bom()
        mo = self._mo(bom, design_params={"material": "glass"})
        vals = mo.copy_data()[0]
        self.assertEqual(
            vals.get("design_param_definition_id"), self.definition.id
        )

    # ── Merge политика ───────────────────────────────────────────────────
    def test_merge_blocks_differing_config(self):
        """Merge на MO-та с РАЗЛИЧЕН конфиг → UserError."""
        bom = self._build_bom()
        mo1 = self._mo(bom, design_params={"material": "glass"})
        mo2 = self._mo(bom, design_params={"material": "wood"})
        with self.assertRaises(UserError):
            (mo1 | mo2)._pre_action_split_merge_hook(merge=True)

    def test_merge_allows_same_config(self):
        """Merge на MO-та с ЕДНАКЪВ конфиг минава хука без грешка."""
        bom = self._build_bom()
        mo1 = self._mo(bom, design_params={"material": "glass"})
        mo2 = self._mo(bom, design_params={"material": "glass"})
        # не трябва да хвърля
        (mo1 | mo2)._pre_action_split_merge_hook(merge=True)

    # ── Контрол на партидата + отпечатък ─────────────────────────────────
    def test_fingerprint_stamped_on_lot(self):
        """MO конфигът се пише върху партидата + отпечатък в note/ref."""
        bom = self._build_bom(product=self.finished_lot)
        lot = self.Lot.create(
            {"name": "MOC-FP", "product_id": self.finished_lot.id}
        )
        mo = self._mo(
            bom,
            product=self.finished_lot,
            design_params={"material": "glass"},
            lot=lot,
        )
        mo._stamp_design_fingerprint()
        # партидата поема конфига (selection пази ЛЕЙБЪЛА → 'Glass')
        self.assertEqual(lot.design_param_definition_id, self.definition)
        self.assertEqual(lot.design_params.get("material"), "Glass")
        # отпечатък: четим блок + къс хеш (видим маркер df:<hash>)
        self.assertIn("Design fingerprint", str(lot.note))
        self.assertTrue(lot.ref, "късият хеш влиза в ref")
        self.assertIn(lot.ref, str(lot.note))

    def test_fingerprint_idempotent(self):
        """Повторно печатане не дублира блока (маркер по хеш)."""
        bom = self._build_bom(product=self.finished_lot)
        lot = self.Lot.create(
            {"name": "MOC-FP2", "product_id": self.finished_lot.id}
        )
        mo = self._mo(
            bom,
            product=self.finished_lot,
            design_params={"material": "wood"},
            lot=lot,
        )
        mo._stamp_design_fingerprint()
        mo._stamp_design_fingerprint()
        self.assertEqual(str(lot.note).count("Design fingerprint"), 1)
