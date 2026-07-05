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
"""Мулти-индустриен guard (D1/D2): get_component_attributes класифицира по
product.attribute.design_role (ДАННИ) — доказваме, че engine-ът работи
еднакво за „врата" (кирилски имена) и „щора" (английски имена) при сетнати
роли, и че БЕЗ роля атрибутът не се класифицира (нула езикови конвенции).
"""
from odoo.tests.common import TransactionCase


class TestAttributeRoles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Attr = env["product.attribute"]
        Val = env["product.attribute.value"]

        def make_component(name, attrs):
            """component template с attribute lines по [(attr, [values])]."""
            tmpl = env["product.template"].create({
                "name": name, "type": "consu",
            })
            for attr, values in attrs:
                env["product.template.attribute.line"].create({
                    "product_tmpl_id": tmpl.id,
                    "attribute_id": attr.id,
                    "value_ids": [(6, 0, values.ids)],
                })
            return tmpl

        def attr(name, role, values=("V1", "V2")):
            a = Attr.create({"name": name, "design_role": role,
                             "create_variant": "no_variant"})
            vals = Val.create([{"name": v, "attribute_id": a.id}
                               for v in values])
            return a, vals

        # „врата": кирилски имена + роли (както Solid след миграцията)
        cls.a_color_bg, v1 = attr("Цвят (тест)", "color")
        cls.a_coat_bg, v2 = attr("Покритие (тест)", "coating")
        cls.a_motif_bg, v3 = attr("Мотив (тест)", "motif")
        door_comp = make_component("D2 Door leaf", [
            (cls.a_color_bg, v1), (cls.a_coat_bg, v2), (cls.a_motif_bg, v3)])

        # „щора": английски имена + СЪЩИТЕ роли — нула езикова зависимост
        cls.a_color_en, w1 = attr("Blind Color", "color")
        cls.a_coat_en, w2 = attr("Blind Finish", "coating")
        blind_comp = make_component("D2 Blind slat pack", [
            (cls.a_color_en, w1), (cls.a_coat_en, w2)])

        # компонент БЕЗ роли → не се класифицира
        cls.a_norole, u1 = attr("Random Property", False)
        plain_comp = make_component("D2 Plain part", [(cls.a_norole, u1)])

        def make_final(name, comps):
            tmpl = env["product.template"].create({
                "name": name, "type": "consu",
            })
            env["mrp.bom"].create({
                "product_tmpl_id": tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                # маркер за матрична BoM (search-ът филтрира по таблица)
                "material_table": False,
                "constraint_table": {
                    "nodes": [
                        {"id": "i", "type": "inputNode", "name": "Req"},
                        {"id": "t", "type": "decisionTableNode", "name": "T0",
                         "content": {"hitPolicy": "collect",
                                     "inputs": [{"id": "x", "name": "x",
                                                 "field": "x"}],
                                     "outputs": [{"id": "y", "name": "y",
                                                  "field": "y"}],
                                     "rules": [{"_id": "r1", "x": "",
                                                "y": "1"}]}},
                        {"id": "o", "type": "outputNode", "name": "Res"},
                    ],
                    "edges": [
                        {"id": "e1", "sourceId": "i", "targetId": "t"},
                        {"id": "e2", "sourceId": "t", "targetId": "o"},
                    ],
                },
                "bom_line_ids": [
                    (0, 0, {"product_id": c.product_variant_id.id,
                            "product_qty": 1.0}) for c in comps
                ],
            })
            return tmpl.product_variant_id

        cls.door = make_final("D2 Door", [door_comp, plain_comp])
        cls.blind = make_final("D2 Blind", [blind_comp, plain_comp])

    def test_door_component_classified_by_role(self):
        comps = self.env["mrp.bom"].get_component_attributes(self.door.id)
        self.assertEqual(len(comps), 1, "само компонентът с color атрибут")
        attrs = {a["name"]: a for a in comps[0]["attributes"]}
        self.assertTrue(attrs["Цвят (тест)"]["isColor"])
        self.assertTrue(attrs["Покритие (тест)"]["isCoating"])
        self.assertTrue(attrs["Мотив (тест)"]["isMotif"])
        # еднозначна двойка: точно 1 coating → paired
        self.assertEqual(attrs["Цвят (тест)"]["pairedCoatingAttrId"],
                         self.a_coat_bg.id)

    def test_blind_component_same_engine_english_names(self):
        comps = self.env["mrp.bom"].get_component_attributes(self.blind.id)
        self.assertEqual(len(comps), 1)
        attrs = {a["name"]: a for a in comps[0]["attributes"]}
        self.assertTrue(attrs["Blind Color"]["isColor"])
        self.assertTrue(attrs["Blind Finish"]["isCoating"])
        self.assertEqual(attrs["Blind Color"]["pairedCoatingAttrId"],
                         self.a_coat_en.id)

    def test_attribute_without_role_not_classified(self):
        for product in (self.door, self.blind):
            comps = self.env["mrp.bom"].get_component_attributes(product.id)
            for comp in comps:
                self.assertNotIn("Random Property",
                                 [a["name"] for a in comp["attributes"]
                                  if a["isColor"] or a["isCoating"]
                                  or a["isMotif"]])
