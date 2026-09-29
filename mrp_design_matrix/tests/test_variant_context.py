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
"""Атрибут с ЕДНА стойност стига до контекста.

`product_template_variant_value_ids` има домейн `value_count > 1`, тоест Odoo
изрязва линиите с една стойност. Двигателят четеше точно него, затова
„Вид врата: Блиндирана“ на BoM 36 никога не влизаше в контекста, а „Модел“
(18 стойности) влизаше. Тестът държи и двата случая в една рецепта.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestVariantContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attr = cls.env["product.attribute"]
        cls.edna = Attr.create({
            "name": "Test Frame Material",
            "create_variant": "always",
            "value_ids": [(0, 0, {"name": "Aluminium"}), (0, 0, {"name": "Wood"})],
        })
        cls.dve = Attr.create({
            "name": "Test Model",
            "create_variant": "always",
            "value_ids": [(0, 0, {"name": "Alpha"}), (0, 0, {"name": "Beta"})],
        })
        cls.tmpl = cls.env["product.template"].create({
            "name": "Test Door",
            "type": "consu",
            "attribute_line_ids": [
                # ЕДНА стойност — точно случаят, който се губеше
                (0, 0, {"attribute_id": cls.edna.id,
                        "value_ids": [(6, 0, cls.edna.value_ids[:1].ids)]}),
                (0, 0, {"attribute_id": cls.dve.id,
                        "value_ids": [(6, 0, cls.dve.value_ids.ids)]}),
            ],
        })
        cls.variant = cls.tmpl.product_variant_ids.filtered(
            lambda p: "Alpha" in p.product_template_attribute_value_ids.mapped("name"))
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.tmpl.id,
            "product_qty": 1.0,
            "variant_context_map": {"frame_material": "Test Frame Material",
                                    "door_model": "Test Model"},
        })

    def _mo(self):
        # `new()` живее само в кеша. Създаден веднъж в setUpClass, губи
        # стойностите си, когато рамката чисти кеша между тестовете: първият
        # тест минаваше, а вторият получаваше празен продукт и празен контекст.
        return self.env["mrp.production"].new({
            "product_id": self.variant.id,
            "bom_id": self.bom.id,
        })

    def test_odoo_izryazva_ednata_stoynost_ot_izchislenoto_pole(self):
        # Предпоставката: ако Odoo някога спре да изрязва, тестът казва защо
        # поправката вече не е нужна, вместо да минава мълчаливо.
        self.assertEqual(len(self.tmpl.product_variant_ids), 2)
        self.assertNotIn(
            "Aluminium", self.variant.product_template_variant_value_ids.mapped("name"))
        self.assertIn(
            "Aluminium", self.variant.product_template_attribute_value_ids.mapped("name"))

    def test_edinichnata_stoynost_stiga_do_konteksta(self):
        ctx = self._mo()._get_variant_context_values(self.bom)
        self.assertEqual(ctx.get("frame_material"), "Aluminium")

    def test_mnozhestvenata_stoynost_ostava(self):
        ctx = self._mo()._get_variant_context_values(self.bom)
        self.assertEqual(ctx.get("door_model"), "Alpha")
