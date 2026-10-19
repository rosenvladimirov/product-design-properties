# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
"""Стандартният продукт вместо изделие по поръчка (ADR sale-order-poc/0027).

Всеки тест носи МУТАЦИЯТА, която го уронва.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models.poc_standard import parse_size_mm
from .common import PocCommon


@tagged("post_install", "-at_install")
class TestStandardProduct(PocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template.alternative_size_codes = "t_length_mm, t_width_mm"
        cls.size = cls.env["product.attribute"].create(
            {"name": "TEST Size", "poc_size_unit": "cm", "create_variant": "always"}
        )
        names = ["50×30", "31×52", "70×40", "45×30"]
        values = cls.env["product.attribute.value"].create(
            [{"name": name, "attribute_id": cls.size.id} for name in names]
        )
        ready = cls.env["product.template"].create(
            {
                "name": "TEST Ready Bag",
                "type": "consu",
                "sale_ok": True,
                "list_price": 0.5,
                "attribute_line_ids": [
                    (0, 0, {"attribute_id": cls.size.id, "value_ids": [(6, 0, values.ids)]})
                ],
            }
        )
        cls.ready = {
            variant.product_template_attribute_value_ids.name: variant
            for variant in ready.product_variant_ids
        }
        # изделие по поръчка в същия размер — не е „готово“
        cls.env["product.template"].create(
            {
                "name": "TEST Made to Order",
                "type": "consu",
                "sale_ok": True,
                "poc_template_id": cls.template.id,
                "attribute_line_ids": [
                    (0, 0, {"attribute_id": cls.size.id, "value_ids": [(6, 0, values[:1].ids)]})
                ],
            }
        )
        cls.handle = cls.env["product.product"].create(
            {"name": "TEST handle", "type": "consu", "sale_ok": True, "list_price": 2.0}
        )
        cls.product.product_tmpl_id.optional_product_ids = cls.handle.product_tmpl_id

    def test_the_size_from_the_attribute_text(self):
        """Числата отпред, единицата от атрибута или от самия текст.

        МУТАЦИЯ: в `parse_size_mm` единицата винаги от атрибута — „см“ в
        текста на мм атрибут дава 40 вместо 400.
        """
        self.assertEqual(parse_size_mm("10,5×10×3", "cm"), [105.0, 100.0, 30.0])
        self.assertEqual(parse_size_mm("400×300×300", "mm"), [400.0, 300.0, 300.0])
        self.assertEqual(
            parse_size_mm("40×30×30 см, трипластно C", "mm"), [400.0, 300.0, 300.0]
        )
        self.assertEqual(parse_size_mm("Ф46 мм", "mm"), [])

    def test_the_closest_standard_products(self):
        """В допуска, със смяна на Д и Ш, подредени по излишъка; без изделията по поръчка.

        МУТАЦИЯ: в `_poc_size_excess` без втората ориентация — 31×52 изпада.
        """
        poc = self._make_poc(t_length_mm=500.0, t_width_mm=300.0)
        names = [c["product"].product_template_attribute_value_ids.name
                 for c in poc._poc_alternatives()]
        self.assertEqual(names, ["50×30", "31×52"])
        self.assertEqual(poc.alternative_product_ids, self.ready["50×30"] | self.ready["31×52"])

    def test_an_unclear_size_still_finds(self):
        """Само една мярка: сравнява се само тя.

        МУТАЦИЯ: в `_poc_alternatives` липсващата мярка спира търсенето —
        без кандидати.
        """
        poc = self._make_poc(t_width_mm=300.0)
        products = poc.alternative_product_ids
        self.assertIn(self.ready["50×30"], products)
        self.assertNotIn(self.ready["70×40"], products)

    def test_no_size_no_alternatives(self):
        poc = self._make_poc()
        self.assertFalse(poc.alternative_product_ids)

    def test_choosing_the_standard_product_replaces_the_line(self):
        """Редът продава готовия по ценовата листа; без съпътстващи; връщането.

        МУТАЦИЯ: в `_poc_companion_lines` без изхода при стандартен — дръжката остава.
        """
        poc = self._make_poc(t_length_mm=500.0, t_width_mm=300.0)
        poc.optional_product_ids = self.handle
        line = poc.sale_line_id
        line.price_unit = 9.99
        self.assertTrue(poc.companion_line_ids)
        chosen = self.ready["50×30"]
        poc.standard_product_id = chosen
        self.assertEqual(line.product_id, chosen)
        self.assertEqual(line.price_unit, 0.5)
        self.assertEqual(poc.configured_product_id, self.product)
        self.assertFalse(poc.companion_line_ids)
        poc.standard_product_id = False
        self.assertEqual(line.product_id, self.product)
        self.assertFalse(poc.configured_product_id)
        self.assertTrue(poc.companion_line_ids)

    def test_confirming_with_a_standard_product(self):
        """Без задължителните параметри и без лот.

        МУТАЦИЯ: в `_poc_confirm` без филтъра — дебелината липсва и
        потвърждаването пада.
        """
        poc = self._make_poc(t_length_mm=500.0, t_width_mm=300.0)
        poc.standard_product_id = self.ready["50×30"]
        poc.order_id.action_confirm()
        self.assertEqual(poc.state, "confirmed")
        self.assertFalse(poc.lot_id)
        move = poc.sale_line_id.move_ids
        self.assertTrue(move)
        self.assertFalse(move.poc_id)

    def test_only_on_a_quotation(self):
        """МУТАЦИЯ: без `_poc_check_standard_allowed` — потвърденият ред сменя артикула."""
        poc = self._make_poc(t_length_mm=500.0, t_width_mm=300.0, t_thickness_um=20.0)
        poc.order_id.action_confirm()
        # нашият отказ, преди ядрото да откаже смяната на артикула
        with self.assertRaisesRegex(UserError, "only while the quotation is a draft"):
            poc.standard_product_id = self.ready["50×30"]
