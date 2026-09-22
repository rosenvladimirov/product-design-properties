# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
"""Надценките на калкулацията са в раздела „Дизайн“, с етикети.

Вмъкнати до `list_price`, Odoo 19 ги рисуваше без етикет в реда на
продажната цена — две голи „0,00“ на всеки артикул (Пакит, 22.09.2026).
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMarkupView(TransactionCase):
    def _arch(self, model):
        views = self.env[model].get_views([(False, "form")])
        return etree.fromstring(views["views"]["form"]["arch"])

    def test_markups_live_in_the_design_tab(self):
        for model in ("product.template", "product.product"):
            arch = self._arch(model)
            for name in ("material_markup_percent", "labor_markup_percent"):
                nodes = arch.xpath(f"//field[@name='{name}']")
                self.assertEqual(len(nodes), 1, f"{model}: {name} once")
                self.assertTrue(
                    nodes[0].xpath("ancestor::page[@name='design_properties_page']"),
                    f"{model}: {name} must be in the Design tab",
                )
                self.assertFalse(
                    nodes[0].xpath("preceding-sibling::field[@name='list_price']"),
                    f"{model}: {name} must not sit in the sales price row",
                )
