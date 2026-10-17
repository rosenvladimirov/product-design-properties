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

    def _switch_template(self):
        """Шаблон със секция „Print“, превключвана от „pos_print“."""
        Param = self.env["sale.order.poc.param"].sudo()
        switch = Param.create({"code": "pos_print", "name": "With print", "param_type": "boolean"})
        colours = Param.create({"code": "pos_colours", "name": "Colours", "param_type": "integer"})
        self.template.sudo().write({"line_ids": [
            (0, 0, {"sequence": 10, "display_type": "line_section", "name": "Print"}),
            (0, 0, {"sequence": 11, "param_id": switch.id, "section_switch": True}),
            (0, 0, {"sequence": 12, "param_id": colours.id}),
        ]})

    def test_switch_and_optional_reach_the_register(self):
        """Превключвателят е в заглавието на секцията, не сред параметрите;
        изключен и записан — секцията губи данните си. Опционалните продукти
        на артикула се избират и пишат.

        МУТАЦИЯ: `_l10n_bg_pos_data` оставя превключвателя сред параметрите.
        """
        Line = self.env["sale.order.poc.template.line"]
        if "section_switch" not in Line._fields:
            self.skipTest("sale_order_poc без превключватели на секции")
        self._switch_template()
        fee = self.create_product("Ribbon", self.categ_basic, 0.5, 1)
        self.configured.product_tmpl_id.sudo().optional_product_ids = fee.product_tmpl_id
        self.open_new_session()
        result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        section = next(s for s in result["poc"]["sections"] if s["title"] == "Print")
        self.assertEqual(section["switch"]["code"], "pos_print")
        self.assertEqual([p["code"] for p in section["params"]], ["pos_colours"])
        self.assertEqual([o["id"] for o in result["poc"]["optional"]["options"]], [fee.id])
        data = self.config.l10n_bg_poc_save(
            result["poc"]["id"], {"pos_print": True, "pos_colours": 2, "__optional": [fee.id]})
        self.assertEqual(self._params(data)["pos_colours"]["value"], 2)
        self.assertEqual(data["optional"]["value"], [fee.id])
        data = self.config.l10n_bg_poc_save(result["poc"]["id"], {"pos_print": False})
        self.assertIn(self._params(data)["pos_colours"]["value"], (None, False))

    # ── Рисунката (sale_order_poc_drawing, О5) ──────────────────────

    def _drawing_template(self, svg=None):
        drawing = self.env["sale.order.poc.drawing"].sudo().create({
            "name": "POS rectangle",
            "code": "pos_rect",
            "svg": svg or (
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<polygon class="body" t-att-points="d.pts(d.rect(0, 0, '
                "d.num(v.get('pos_width_mm')), 100))\"/>"
                "<text class=\"material\" t-out=\"v.get('pos_material')\"/>"
                "<text class=\"printer\" t-out=\"v.get('pos_printer')\"/>"
                "</svg>"
            ),
        })
        self.template.sudo().write({
            "drawing_template_id": drawing.id,
            "drawing_defaults": "pos_width_mm=300",
            "drawing_caption": "Width {{ pos_width_mm }}",
        })
        return drawing

    def test_picture_preview_follows_unsaved_values(self):
        """Касата: `l10n_bg_poc_picture(poc_id, {размер: X})` рисува с X, без запис;
        many2one идва като id, селекцията — като ключ (SPEC § 4, т. 8).

        МУТАЦИЯ: прегледът вика `_poc_drawing()` без `values`.
        """
        self._drawing_template()
        self.open_new_session()
        result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        poc = self.env["sale.order.poc"].browse(result["poc"]["id"])
        # отварянето — с подразбирането
        self.assertIn("300.0,0.0", str(result["poc"]["picture"]["svg"]))
        self.assertEqual(result["poc"]["picture"]["caption"], "Width 300 mm")
        picture = self.config.l10n_bg_poc_picture(poc.id, {
            "pos_width_mm": 640,
            "pos_material": "hdpe",
            "pos_printer": self.b2b_company.id,
            "unknown_code": 5,
        })
        svg = str(picture["svg"])
        self.assertIn("640.0,0.0", svg)
        self.assertIn('<text class="material">hdpe</text>', svg)
        self.assertIn(self.b2b_company.name, svg)
        self.assertEqual(picture["caption"], "Width 640 mm")
        # нищо не е записано
        self.assertIsNone(poc._poc_values()["pos_width_mm"])
        self.assertEqual(poc._poc_values()["pos_material"], "ldpe")

    def test_broken_drawing_does_not_break_the_register(self):
        """Счупеният шаблон: касата отваря и прерисува без картинка, не пада
        (SPEC § 4, т. 5).

        МУТАЦИЯ: махни try/except в `_render_svg`.
        """
        self._drawing_template('<svg xmlns="http://www.w3.org/2000/svg"><t t-out="d.nope()"/></svg>')
        self.open_new_session()
        logger = "odoo.addons.sale_order_poc_drawing.models.sale_order_poc_drawing"
        with self.assertLogs(logger, "WARNING"):
            result = self.config.l10n_bg_poc_open(self._payload(self.configured), "line-1")
        self.assertFalse(result["poc"]["picture"])
        with self.assertLogs(logger, "WARNING"):
            self.assertFalse(self.config.l10n_bg_poc_picture(result["poc"]["id"], {"pos_width_mm": 5}))
