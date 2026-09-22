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
"""Параметрите на POC във формата на MO (ADR sale-order-poc/0018)."""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestMoParams(PocMrpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lines = cls.template.line_ids
        cls.line_width = lines.filtered(lambda l: l.param_id == cls.p_width)
        cls.line_material = lines.filtered(lambda l: l.param_id == cls.p_material)
        (cls.line_width | cls.line_material).show_in_production = True

    def _read_names(self, production, fname):
        """Имената на параметрите, както ги получава клиентът, без разделителите."""
        values = production.read([fname])[0][fname]
        return {v["name"]: v.get("value") for v in values if v["type"] != "separator"}

    def test_line_takes_the_default_from_the_dictionary(self):
        param = self.env["sale.order.poc.param"].create(
            {
                "code": "t_mo_note",
                "name": "Shop Note",
                "param_type": "char",
                "show_in_production": True,
            }
        )
        plain = self.env["sale.order.poc.param"].create(
            {"code": "t_mo_plain", "name": "Plain", "param_type": "char"}
        )
        self.template.line_ids = [
            (0, 0, {"sequence": 20, "param_id": param.id}),
            (0, 0, {"sequence": 21, "param_id": plain.id}),
        ]
        line = self.template.line_ids.filtered(lambda l: l.param_id == param)
        line_plain = self.template.line_ids.filtered(lambda l: l.param_id == plain)
        self.assertTrue(line.show_in_production)
        self.assertFalse(line_plain.show_in_production)
        # редът може да каже друго от речника
        line.show_in_production = False
        self.assertFalse(line.show_in_production)

    def test_definition_keeps_only_the_marked_lines(self):
        definition = self.template.mo_param_definition
        names = [entry["name"] for entry in definition]
        # разделителят „Size“ стои пред първия показан параметър и е разгънат
        self.assertEqual(definition[0]["type"], "separator")
        self.assertFalse(definition[0]["fold_by_default"])
        self.assertEqual(names[1:], ["t_width_mm", "t_material"])

    def test_definition_follows_the_dictionary(self):
        """Преименуван параметър стига до схемата на MO — зависимостта върви
        през схемата на шаблона."""
        self.p_width.name = "Width Renamed"
        entry = next(
            e for e in self.template.mo_param_definition if e["name"] == "t_width_mm"
        )
        self.assertEqual(entry["string"], "Width Renamed")

    def test_mo_shows_only_the_marked_values(self):
        _order, poc = self._confirmed_order(qty=10.0, width=300.0, length=500.0)
        production = poc.production_ids
        shown = self._read_names(production, "poc_mo_params")
        everything = self._read_names(production, "poc_params")
        self.assertEqual(set(shown), {"t_width_mm", "t_material"})
        self.assertEqual(shown["t_width_mm"], 300.0)
        # дължината е в POC, но не е отметната
        self.assertEqual(everything["t_length_mm"], 500.0)
        self.assertNotIn("t_length_mm", shown)

    def test_nothing_marked_shows_nothing(self):
        (self.line_width | self.line_material).show_in_production = False
        _order, poc = self._confirmed_order(qty=10.0)
        self.assertFalse(self.template.mo_param_definition)
        self.assertFalse(poc.production_ids.read(["poc_mo_params"])[0]["poc_mo_params"])

    def test_placeholder_becomes_the_parameters(self):
        view = self.env["mrp.production"].get_view(view_type="form")
        arch = etree.fromstring(view["arch"])
        self.assertFalse(arch.xpath("//*[@name='poc_mo_params_placeholder']"))
        placed = arch.xpath(
            "//group[@name='group_extra_info']/field[@name='user_id']"
            "/following-sibling::*[1][self::field][@name='poc_mo_params']"
        )
        self.assertEqual(len(placed), 1, "the parameters are not under the responsible")
        self.assertEqual(placed[0].get("invisible"), "not poc_mo_params")

    def test_other_company_sees_the_values(self):
        """MO във фирмата производител вижда POC на продаващата фирма
        (Солид: СДЦ продава, Продакшън произвежда)."""
        _order, poc = self._confirmed_order(qty=10.0, width=300.0)
        maker = self.env["res.company"].create({"name": "POC Maker"})
        worker = new_test_user(
            self.env,
            login="poc_mo_maker",
            groups="mrp.group_mrp_user",
            company_id=maker.id,
            company_ids=[(6, 0, maker.ids)],
        )
        production = (
            self.env["mrp.production"]
            .with_company(maker)
            .create(
                {
                    "product_id": self.product.id,
                    "product_qty": 1.0,
                    "company_id": maker.id,
                }
            )
        )
        production.poc_id = poc
        # самият POC е на чужда фирма: пряко не се чете
        with self.assertRaises(AccessError):
            poc.with_user(worker).read(["params"])
        seen = production.with_user(worker).with_company(maker)
        shown = self._read_names(seen, "poc_mo_params")
        self.assertEqual(shown["t_width_mm"], 300.0)
