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
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_bg_pos_b2b.tests.common import B2bPosCommon


@tagged("post_install", "-at_install")
class TestPocPos(B2bPosCommon):
    """Конфигурацията на ред на едро в касата (ADR pos-b2b-wholesale/0004)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # касиерът: Продажби + конфигурации (README/CONFIGURE)
        cls.env.user.group_ids += cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.group_ids += cls.env.ref("sale_order_poc.group_poc_user")
        # речникът и шаблонът са настройка — прави ги администратор
        Param = cls.env["sale.order.poc.param"].sudo()
        cls.p_width = Param.create(
            {"code": "pos_width_mm", "name": "Width", "param_type": "float", "suffix": "mm"}
        )
        cls.p_material = Param.create({
            "code": "pos_material",
            "name": "Material",
            "param_type": "selection",
            "default_value": "ldpe",
            "option_ids": [
                (0, 0, {"key": "ldpe", "name": "LDPE", "sequence": 1}),
                (0, 0, {"key": "hdpe", "name": "HDPE", "sequence": 2}),
            ],
        })
        cls.p_printer = Param.create({
            "code": "pos_printer",
            "name": "Printer",
            "param_type": "many2one",
            "comodel": "res.partner",
        })
        cls.p_double = Param.create(
            {"code": "pos_double_mm", "name": "Double width", "param_type": "float"}
        )
        cls.template = cls.env["sale.order.poc.template"].sudo().create({
            "code": "pos_bag",
            "name": "POS Bag",
            "line_ids": [
                (0, 0, {"sequence": 1, "display_type": "line_section", "name": "Size"}),
                (0, 0, {"sequence": 2, "param_id": cls.p_width.id}),
                (0, 0, {"sequence": 3, "param_id": cls.p_material.id}),
                (0, 0, {"sequence": 4, "param_id": cls.p_printer.id}),
                (0, 0, {
                    "sequence": 5,
                    "param_id": cls.p_double.id,
                    "formula": "result = pos_width_mm * 2",
                }),
            ],
        })

    def setUp(self):
        super().setUp()
        self.configured = self.create_product("Configured Bag", self.categ_basic, 2.0, 1)
        self.configured.product_tmpl_id.sudo().poc_template_id = self.template

    def _payload(self, product, **kwargs):
        payload = {
            "partner_id": self.b2b_company.id,
            "lines": [{"uuid": "line-1", "product_id": product.id, "qty": 10,
                       "price_unit": 2.0, "discount": 0}],
        }
        payload.update(kwargs)
        return payload

    def _params(self, data):
        return {p["code"]: p for s in data["sections"] for p in s["params"]}

    def test_open_creates_configuration(self):
        self.open_new_session()
        result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        poc = self.env["sale.order.poc"].browse(result["poc"]["id"])
        self.assertEqual(poc.sale_line_id.l10n_bg_pos_line_uuid, "line-1")
        params = self._params(result["poc"])
        self.assertEqual(params["pos_material"]["value"], "ldpe")
        self.assertEqual(
            [o["key"] for o in params["pos_material"]["options"]], ["ldpe", "hdpe"]
        )
        self.assertIn(self.b2b_company.id, [o["id"] for o in params["pos_printer"]["options"]])
        self.assertEqual(params["pos_width_mm"]["suffix"], "mm")
        # втори път — същата конфигурация, не нова
        again = self.config.l10n_bg_poc_open(
            self._payload(self.configured, sale_order_id=result["quotation"]["id"]), "line-1"
        )
        self.assertEqual(again["poc"]["id"], poc.id)

    def test_save_writes_and_computes(self):
        self.open_new_session()
        result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        data = self.config.l10n_bg_poc_save(result["poc"]["id"], {
            "pos_width_mm": 350,
            "pos_material": "hdpe",
            "pos_printer": self.b2b_company.id,
            "unknown_code": 1,
        })
        params = self._params(data)
        self.assertEqual(params["pos_width_mm"]["value"], 350)
        self.assertEqual(params["pos_material"]["value"], "hdpe")
        self.assertEqual(params["pos_printer"]["value"], self.b2b_company.id)
        # формулата е пресметната (Compute)
        self.assertEqual(params["pos_double_mm"]["value"], 700)

    def test_configured_line_keeps_its_price(self):
        self.open_new_session()
        result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        so_line = self.env["sale.order.poc"].browse(result["poc"]["id"]).sale_line_id
        so_line.price_unit = 7.5  # цената от конфигурацията
        self.config.l10n_bg_b2b_save_quotation(
            self._payload(self.configured, sale_order_id=result["quotation"]["id"])
        )
        self.assertEqual(so_line.price_unit, 7.5)

    def test_product_without_template_is_refused(self):
        self.open_new_session()
        with self.assertRaises(UserError):
            self.config.l10n_bg_poc_open(self._payload(self.product1), "line-1")

    def test_companion_lines_reach_the_register(self):
        """Допълнителните редове (сито, дръжки…) идват в касата с постоянен ключ.

        Запазването на офертата от касата с този ключ обновява СЪЩИЯ ред, не
        прави втори; махнатото допълнение изчезва и от данните за касата.

        МУТАЦИЯ: `_l10n_bg_pos_companions` не пише ключа на реда — второто
        запазване ражда втори ред „Fee“.
        """
        from unittest.mock import patch

        Poc = self.env["sale.order.poc"]
        if "companion_line_ids" not in Poc._fields:
            self.skipTest("sale_order_poc без допълнителни редове (ADR sale-order-poc/0022)")
        self.open_new_session()
        fee = self.create_product("Fee", self.categ_basic, 3.0, 1)
        wanted = [True]

        def companions(poc):
            lines = []
            if wanted[0]:
                lines.append({"key": "fee", "product": fee, "qty": 10.0, "price_unit": 3.0})
            return lines

        with patch.object(type(Poc), "_poc_companion_lines", companions):
            result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
            data = self.config.l10n_bg_poc_save(result["poc"]["id"], {})
            poc = Poc.browse(data["id"])
            uuid = "poc%d-fee" % poc.id
            self.assertEqual(data["companion_prefix"], "poc%d-" % poc.id)
            self.assertEqual(
                [(c["uuid"], c["product_id"], c["qty"], c["price_unit"]) for c in data["companions"]],
                [(uuid, fee.id, 10.0, 3.0)],
            )
            # касата праща реда обратно със същия ключ ⇒ един ред, не два
            payload = self._payload(self.configured, sale_order_id=result["quotation"]["id"])
            payload["lines"].append(
                {"uuid": uuid, "product_id": fee.id, "qty": 10, "price_unit": 3.0, "discount": 0})
            self.config.l10n_bg_b2b_save_quotation(payload)
            order = poc.sale_line_id.order_id
            self.assertEqual(len(order.order_line.filtered(lambda l: l.product_id == fee)), 1)
            # допълнението махнато ⇒ няма го и в данните за касата
            wanted[0] = False
            data = self.config.l10n_bg_poc_save(poc.id, {})
            self.assertEqual(data["companions"], [])
            self.assertFalse(order.order_line.filtered(lambda l: l.product_id == fee))
