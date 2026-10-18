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
"""Опционалните продукти и превключвателят на секция (ADR sale-order-poc/0026).

Двата механизма дойдоха от копието на Пакит, тествани там само през
фирмените модули; тук — в общия модул. Всеки тест носи МУТАЦИЯТА, която го
уронва.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestOptionalProducts(PocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.handle = Product.create(
            {"name": "TEST handle", "type": "consu", "sale_ok": True, "list_price": 2.0}
        )
        cls.design = Product.create(
            {
                "name": "TEST design",
                "type": "service",
                "sale_ok": True,
                "list_price": 40.0,
                "poc_optional_per_order": True,
            }
        )
        cls.stranger = Product.create(
            {"name": "TEST not optional", "type": "consu", "sale_ok": True}
        )
        cls.product.product_tmpl_id.optional_product_ids = (
            cls.handle.product_tmpl_id | cls.design.product_tmpl_id
        )

    def _optional_lines(self, order):
        return order.order_line.filtered("poc_companion_of_id")

    def test_optional_product_per_unit_follows_the_quantity(self):
        """Опционален продукт „на брой“ — ред с количеството на изделието.

        МУТАЦИЯ: в `_poc_companion_lines` количеството винаги 1.0 — редът е 1, не 250.
        """
        poc = self._make_poc(order=self._make_order(qty=250.0))
        poc.optional_product_ids = self.handle
        poc._poc_compute_derived()
        line = self._optional_lines(poc.order_id)
        self.assertEqual(line.product_id, self.handle)
        self.assertEqual(line.product_uom_qty, 250.0)

    def test_optional_product_once_per_order(self):
        """„Веднъж за поръчката“ — един ред с количество 1, независимо от тиража.

        МУТАЦИЯ: пренебрегни `poc_optional_per_order` — количеството става 250.
        """
        poc = self._make_poc(order=self._make_order(qty=250.0))
        poc.optional_product_ids = self.design
        poc._poc_compute_derived()
        line = self._optional_lines(poc.order_id)
        self.assertEqual(line.product_id, self.design)
        self.assertEqual(line.product_uom_qty, 1.0)

    def test_only_the_products_optional_products_are_allowed(self):
        """Чужд продукт не може да е опционален за конфигурацията.

        МУТАЦИЯ: махни `_check_optional_products` — записът минава.
        """
        poc = self._make_poc()
        with self.assertRaises(ValidationError):
            poc.optional_product_ids = self.stranger


@tagged("post_install", "-at_install")
class TestSectionSwitch(PocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env["sale.order.poc.param"]
        cls.p_print = Param.create(
            {"code": "t_has_print", "name": "With Print", "param_type": "boolean"}
        )
        cls.p_ink = Param.create(
            {"code": "t_ink_colours", "name": "Ink Colours", "param_type": "float"}
        )
        cls.template.write(
            {
                "line_ids": [
                    (0, 0, {"sequence": 20, "display_type": "line_section", "name": "Print"}),
                    (0, 0, {"sequence": 21, "param_id": cls.p_print.id,
                            "section_switch": True}),
                    (0, 0, {"sequence": 22, "param_id": cls.p_ink.id}),
                ]
            }
        )

    def test_switched_off_section_loses_its_values(self):
        """Изключена секция губи стойностите си — не носи стари в партидата.

        МУТАЦИЯ: `_poc_switched_off_codes` връща празно — цветовете остават 2.
        """
        poc = self._make_poc(t_has_print=True, t_ink_colours=2.0,
                             t_width_mm=300.0, t_length_mm=500.0, t_thickness_um=20.0)
        self.assertEqual(poc._poc_values().get("t_ink_colours"), 2.0)
        poc._poc_set_params({"t_has_print": False})
        poc._poc_compute_derived()
        self.assertFalse(poc._poc_values().get("t_ink_colours"))

    def test_switched_on_section_keeps_its_values(self):
        """Включената секция пази стойностите си.

        МУТАЦИЯ: изчиствай секцията независимо от превключвателя — цветовете изчезват.
        """
        poc = self._make_poc(t_has_print=True, t_ink_colours=2.0,
                             t_width_mm=300.0, t_length_mm=500.0, t_thickness_um=20.0)
        poc._poc_compute_derived()
        self.assertEqual(poc._poc_values().get("t_ink_colours"), 2.0)
