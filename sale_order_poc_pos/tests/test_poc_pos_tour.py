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
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestPocPosTour(TestPointOfSaleHttpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        bg = env.ref("base.bg")
        company = cls.main_pos_config.company_id
        company.country_id = bg
        company.account_fiscal_country_id = bg
        cls.pos_user.group_ids += env.ref("l10n_bg_pos_b2b.group_pos_b2b")
        cls.pos_user.group_ids += env.ref("sales_team.group_sale_salesman")
        cls.pos_user.group_ids += env.ref("sale_order_poc.group_poc_user")
        cls.buyer = env["res.partner"].create({
            "name": "ET Petrov Trade",
            "l10n_bg_uic": "831826092",
            "l10n_bg_uic_type": "bg_uic",
            "street": "3 Shipka Str",
            "city": "Sofia",
            "country_id": bg.id,
        })
        Param = env["sale.order.poc.param"].sudo()
        width = Param.create(
            {"code": "pos_width_mm", "name": "Width", "param_type": "float", "suffix": "mm"}
        )
        material = Param.create({
            "code": "pos_material",
            "name": "Material",
            "param_type": "selection",
            "default_value": "ldpe",
            "option_ids": [
                (0, 0, {"key": "ldpe", "name": "LDPE", "sequence": 1}),
                (0, 0, {"key": "hdpe", "name": "HDPE", "sequence": 2}),
            ],
        })
        double = Param.create(
            {"code": "pos_double_mm", "name": "Double width", "param_type": "float"}
        )
        template = env["sale.order.poc.template"].sudo().create({
            "code": "pos_bag",
            "name": "POS Bag",
            "line_ids": [
                (0, 0, {"sequence": 1, "display_type": "line_section", "name": "Size"}),
                (0, 0, {"sequence": 2, "param_id": width.id}),
                (0, 0, {"sequence": 3, "param_id": material.id}),
                (0, 0, {
                    "sequence": 4,
                    "param_id": double.id,
                    "formula": "result = pos_width_mm * 2",
                }),
            ],
        })
        cls.configured = env["product.product"].create({
            "name": "Configured Bag",
            "type": "consu",
            "list_price": 2.0,
            "available_in_pos": True,
            # с партида: касата НЕ пита за нея — идва от конфигурацията
            "is_storable": True,
            "tracking": "lot",
        })
        cls.configured.product_tmpl_id.sudo().poc_template_id = template

    # Т-POC-1: стъпваш на ред с конфигурация → редакторът в десния екран;
    # промяна + Compute → формулата е пресметната, конфигурацията е записана
    def test_tour_poc_editor(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("sale_order_poc_pos_editor")
        poc = self.env["sale.order.poc"].search([("partner_id", "=", self.buyer.id)])
        self.assertEqual(len(poc), 1)
        values = poc._poc_values()
        self.assertEqual(values["pos_width_mm"], 350)
        self.assertEqual(values["pos_material"], "hdpe")
        self.assertEqual(values["pos_double_mm"], 700)

    # Т-POC-2: допълнителният ред на конфигурацията идва в касата
    def test_tour_poc_companion(self):
        from unittest.mock import patch

        Poc = self.env["sale.order.poc"]
        if "companion_line_ids" not in Poc._fields:
            self.skipTest("sale_order_poc без допълнителни редове (ADR sale-order-poc/0022)")
        # НЕ е в касата: касата го зарежда сама
        fee = self.env["product.product"].create({
            "name": "Setup Fee (test)", "type": "service", "list_price": 5.0,
            "available_in_pos": False,
        })

        def companions(poc):
            # идва чак след промяна + Compute — проверява пътя на „Compute“
            if poc._poc_values().get("pos_width_mm") != 350:
                return []
            return [{"key": "fee", "product": fee, "qty": 1.0, "price_unit": 5.0}]

        with patch.object(type(Poc), "_poc_companion_lines", companions):
            self.main_pos_config.with_user(self.pos_user).open_ui()
            self.start_pos_tour("sale_order_poc_pos_companion")
        poc = Poc.search([("partner_id", "=", self.buyer.id)])
        fee_lines = poc.sale_line_id.order_id.order_line.filtered(lambda l: l.product_id == fee)
        self.assertEqual(len(fee_lines), 1)
        self.assertEqual(fee_lines.l10n_bg_pos_line_uuid, "poc%d-fee" % poc.id)

    # Т-POC-3: превключвателят горе и опционалният продукт като ред
    def test_tour_poc_switch(self):
        env = self.env
        Line = env["sale.order.poc.template.line"]
        if "section_switch" not in Line._fields:
            self.skipTest("sale_order_poc без превключватели на секции")
        Param = env["sale.order.poc.param"].sudo()
        switch = Param.create({"code": "pos_print", "name": "With print", "param_type": "boolean"})
        colours = Param.create({"code": "pos_colours", "name": "Colours", "param_type": "integer"})
        template = self.configured.product_tmpl_id.poc_template_id.sudo()
        template.write({"line_ids": [
            (0, 0, {"sequence": 10, "display_type": "line_section", "name": "Print"}),
            (0, 0, {"sequence": 11, "param_id": switch.id, "section_switch": True}),
            (0, 0, {"sequence": 12, "param_id": colours.id}),
        ]})
        ribbon = env["product.product"].create({
            "name": "Ribbon (test)", "type": "consu", "list_price": 0.5,
            "available_in_pos": False,
        })
        self.configured.product_tmpl_id.sudo().optional_product_ids = ribbon.product_tmpl_id
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("sale_order_poc_pos_switch")
        poc = env["sale.order.poc"].search([("partner_id", "=", self.buyer.id)])
        values = poc._poc_values()
        self.assertIs(values["pos_print"], True)
        self.assertEqual(values["pos_colours"], 2)
        self.assertEqual(poc.optional_product_ids, ribbon)
