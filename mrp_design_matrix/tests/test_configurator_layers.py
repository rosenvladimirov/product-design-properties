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
"""Слоевете на конфигуратора от 18.0 (фазите A–E) на 19.0.

TΠ (достъпност), TΦ (каскада + derive_expression + lookup таблици), TΩ
(многоинстанционни изделия), TΛ (UX подсказки), живата симулация на
рецептата и T3 продължителността по израз. Двигателят на ZEN се подменя:
тук се мери договорът около него — нормализацията, предимството
рецепта → шаблон и изчислението на изразите — не самият двигател.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.base_zen_decision.models.zen_engine import ZenRunner

# Най-малкият граф, който write-time валидацията на T0 приема.
_EMPTY_GRAPH = {
    "nodes": [
        {"id": "in", "type": "inputNode", "name": "Request"},
        {"id": "out", "type": "outputNode", "name": "Response"},
    ],
    "edges": [{"id": "e1", "sourceId": "in", "targetId": "out"}],
}
# Таблица-маркер: съдържанието не се оценява (двигателят е подменен), но
# полето трябва да е непразно, за да се стигне до оценката.
_MARKER = {"nodes": [{"id": "t", "type": "decisionTableNode",
                      "content": {"hitPolicy": "collect", "inputs": [],
                                  "outputs": [], "rules": []}}]}


@tagged("post_install", "-at_install")
class TestConfiguratorLayers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["mrp.matrix.template"]
        cls.template = cls.Template.create({
            "name": "Layers test template",
            "availability_table": _MARKER,
            "cascade_table": _MARKER,
            "multiplicity_table": _MARKER,
            "layout_table": _MARKER,
            "lookup_tables": {
                "box_by_height": {"std": {"40": [[1200, 165], [1800, 180], [2600, 205]]}},
                "flat": {"a": "A"},
            },
        })
        cls.comp = cls.env["product.product"].create(
            {"name": "Layers slat", "standard_price": 2.0})
        cls.product = cls.env["product.product"].create(
            {"name": "Layers shutter", "is_storable": True})
        # quantity_formula на реда е изчислено поле от шаблона на формулата
        cls.formula = cls.env["mrp.bom.line.formula.template"].create({
            "name": "Layers slat length",
            "quantity_formula": "quantity = width / 1000.0 * 2",
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "product_qty": 1.0,
            "matrix_template_id": cls.template.id,
            "bom_line_ids": [
                (0, 0, {"product_id": cls.comp.id, "product_qty": 1.0,
                        "formula_template_id": cls.formula.id}),
                (0, 0, {"product_id": cls.comp.id, "product_qty": 3.0}),
            ],
        })

    # ── нормализаторите ───────────────────────────────────────────────────

    def test_availability_merge(self):
        """visible/enabled се натрупват с И, allowed_values се пресичат,
        default_override — последното печели."""
        out = self.Template._normalize_availability([
            {"param": "box", "visible": True, "allowed_values": [165, 180, 205]},
            {"param": "box", "visible": False, "allowed_values": [180, 205],
             "default_override": 180},
            {"param": "box", "default_override": 205},
            {"no_param": 1},
        ])
        self.assertEqual(out, {"box": {"visible": False,
                                       "allowed_values": [180, 205],
                                       "default_override": 205}})

    def test_cascade_last_wins_and_drops_empty(self):
        out = self.Template._normalize_cascade({"result": [
            {"target_param": "color_box", "copy_from": "main_color",
             "only_if_empty": 1},
            {"target_param": "color_box", "derive_value": ""},
            {"target_param": "color_slat", "derive_value": "white",
             "only_if_empty": False},
        ]})
        self.assertEqual(out, {
            "color_box": {"copy_from": "main_color", "only_if_empty": True},
            "color_slat": {"derive_value": "white", "only_if_empty": False},
        })

    def test_multiplicity_first_match(self):
        out = self.Template._normalize_multiplicity([
            {"count_param": "shutter_count", "per_instance_params": ["width", "height"],
             "aggregator": "sum", "skip_when": ""},
            {"count_param": "other"},
        ])
        self.assertEqual(out, {"count_param": "shutter_count",
                               "per_instance_params": ["width", "height"],
                               "aggregator": "sum"})

    def test_layout_customer_visible_is_bool(self):
        out = self.Template._normalize_layout([
            {"param": "color_rope", "customer_visible": 0, "section": "colors"},
            {"param": "color_rope", "widget_hint": "color_picker"},
        ])
        self.assertEqual(out, {"color_rope": {"customer_visible": False,
                                              "section": "colors",
                                              "widget_hint": "color_picker"}})

    # ── lookup() ──────────────────────────────────────────────────────────

    def test_lookup_threshold_and_dict(self):
        lookup = self.Template._make_lookup(self.template.lookup_tables)
        # първият праг >= входа
        self.assertEqual(lookup("box_by_height", "std", 40, 1500), 180)
        self.assertEqual(lookup("box_by_height", "std", 40, 1200), 165)
        self.assertIsNone(lookup("box_by_height", "std", 40, 3000))
        self.assertEqual(lookup("flat", "a"), "A")
        self.assertIsNone(lookup("missing", "a"))
        self.assertIsNone(lookup("box_by_height", "std", "нечисло"))

    # ── TΦ: изразът се изчислява на сървъра ───────────────────────────────

    def test_cascade_expression_on_template(self):
        raw = [{"target_param": "box_size",
                "derive_expression": "lookup('box_by_height', model, slat, height)",
                "only_if_empty": False}]
        with patch.object(ZenRunner, "evaluate", return_value=raw) as zen:
            out = self.template._evaluate_cascade(
                "Height (mm)", {"model": "std", "slat": 40, "height": 1700})
        self.assertEqual(out, {"box_size": {"derive_value": 180,
                                            "only_if_empty": False}})
        # changed_param влиза в контекста на двигателя
        self.assertEqual(zen.call_args.args[1]["changed_param"], "Height (mm)")

    def test_cascade_bad_expression_is_skipped(self):
        raw = [{"target_param": "x", "derive_expression": "1 / 0"}]
        with patch.object(ZenRunner, "evaluate", return_value=raw):
            out = self.template._evaluate_cascade("y", {})
        self.assertEqual(out, {"x": {}})

    def test_bom_falls_back_to_template_tables(self):
        """Рецепта без свои таблици чете тези на шаблона (TΠ, TΦ + lookup)."""
        raw_av = [{"param": "axis", "allowed_values": [40, 60]}]
        with patch.object(ZenRunner, "evaluate", return_value=raw_av):
            self.assertEqual(
                self.env["mrp.bom"].configurator_evaluate_availability(self.bom.id, {}),
                {"axis": {"allowed_values": [40, 60]}})
        raw_c = [{"target_param": "box", "derive_expression": "lookup('flat', 'a')"}]
        with patch.object(ZenRunner, "evaluate", return_value=raw_c):
            self.assertEqual(
                self.env["mrp.bom"].configurator_evaluate_cascade(self.bom.id, "p", {}),
                {"box": {"derive_value": "A"}})

    def test_bom_meta_and_validation(self):
        meta = self.env["mrp.bom"].configurator_get_bom_meta(self.product.id)
        self.assertEqual(meta, {"bom_id": self.bom.id, "has_availability": True})
        raw = [{"param": "box_size", "allowed_values": [180, 205],
                "default_override": 180},
               {"param": "main_color", "allowed_values": ["RAL9016"]},
               {"param": "color_box", "allowed_values": ["RAL9016"]}]
        with patch.object(ZenRunner, "evaluate", return_value=raw):
            violations = self.env["mrp.bom"].configurator_validate_availability(
                self.product.id,
                {"box_size": 165, "main_color": "oak", "color_box": "oak"})
        # кутията + ЕДИН ред за цветовете
        self.assertEqual([v["param"] for v in violations], ["box_size", "main_color"])
        self.assertIn("180/205", violations[0]["message"])

    def test_load_from_template_copies_layers(self):
        bom = self.bom.copy()
        bom.action_load_from_template()
        self.assertEqual(bom.lookup_tables, self.template.lookup_tables)
        for fname in ("availability_table", "cascade_table",
                      "multiplicity_table", "layout_table"):
            self.assertTrue(bom[fname], fname)

    # ── TΩ: стойностите по инстанция ──────────────────────────────────────

    def test_multi_instance_pairs(self):
        lot = self.env["stock.lot"].create({
            "name": "LAYERS-1",
            "product_id": self.product.id,
            "multi_instance_data": [
                {"width": 1000, "height": 1500},
                {"Width": 900},
                {"width": 800, "height": 1400},
            ],
        })
        self.assertEqual(lot.multi_get_per_instance_pairs(["width", "height"]),
                         [(1000, 1500), (800, 1400)])

    # ── живата симулация ──────────────────────────────────────────────────

    def test_simulate_with_params_per_panel(self):
        rich = [{"name": "u1", "string": "Width (mm)", "value": 1000},
                {"name": "u2", "string": "shutter_count", "value": 2}]
        sim = self.bom.simulate_with_params(rich, 1.0, [(1000, 1500), (500, 1500)])
        self.assertEqual(sim["panels"], 2)
        formula_line, fixed_line = sim["lines"]
        # 2 × 1.0 + 2 × 0.5 по панел
        self.assertAlmostEqual(formula_line["qty"], 3.0)
        self.assertEqual([c["L_mm"] for c in formula_line["cuts"]], [1000, 500])
        self.assertEqual(fixed_line["qty"], 3.0)
        self.assertAlmostEqual(sim["total_material"], 12.0)
        # без двойки — един панел, width от етикета
        sim1 = self.env["mrp.bom"].simulate_for_variant(self.product.id, rich)
        self.assertAlmostEqual(sim1["lines"][0]["qty"], 2.0)
        self.assertEqual(sim1["panels"], 1)

    # ── T3: продължителност по израз ──────────────────────────────────────

    def test_t3_duration_expression(self):
        dur = self.env["mrp.production"]._eval_matrix_duration
        self.assertEqual(dur(12, {}), 12.0)
        self.assertEqual(dur('"7.5"', {}), 7.5)
        self.assertEqual(dur("width / 100 + 2", {"width": 1000}), 12.0)
        self.assertEqual(dur("max(5, height / 300)", {"height": 1200}), 5.0)
        self.assertEqual(dur("nonexistent * 2", {}), 0.0)
        self.assertEqual(dur(False, {}), 0.0)
