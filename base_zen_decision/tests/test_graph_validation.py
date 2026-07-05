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
"""Тестове на validate_graph/normalize_jdm_graph (D2) — щитът срещу
T3=[] класа инциденти (счупен/плосък граф, който zen-engine приема
мълчаливо и връща празно за всеки контекст). Чисти функции — без DB.
"""
from odoo.tests.common import BaseCase

from odoo.addons.base_zen_decision.models.zen_engine import (
    normalize_jdm_graph,
    validate_graph,
)


def _full_graph():
    return {
        "nodes": [
            {"id": "in1", "type": "inputNode", "name": "Request"},
            {"id": "dt1", "type": "decisionTableNode", "name": "T",
             "content": {"hitPolicy": "collect",
                         "inputs": [{"id": "a", "name": "a", "field": "a"}],
                         "outputs": [{"id": "b", "name": "b", "field": "b"}],
                         "rules": [{"_id": "r1", "a": "> 0", "b": "1"}]}},
            {"id": "out1", "type": "outputNode", "name": "Response"},
        ],
        "edges": [
            {"id": "e1", "sourceId": "in1", "targetId": "dt1"},
            {"id": "e2", "sourceId": "dt1", "targetId": "out1"},
        ],
    }


def _flat_legacy():
    # форматът от заварените шаблони (коренът на T3=[] инцидента)
    return {
        "nodes": [{
            "id": "t0-x", "name": "T0", "type": "decisionTable",
            "content": {"hitPolicy": "collect",
                        "inputs": [{"id": "w", "name": "width"}],
                        "outputs": [{"id": "m", "name": "message"}],
                        "rules": [{"w": "< 900", "m": '"too small"'}]},
        }],
    }


class TestValidateGraph(BaseCase):

    def test_valid_graph_passes(self):
        self.assertEqual(validate_graph(_full_graph()), [])

    def test_empty_is_legit(self):
        self.assertEqual(validate_graph(False), [])
        self.assertEqual(validate_graph(None), [])

    def test_flat_legacy_rejected(self):
        errs = validate_graph(_flat_legacy())
        self.assertTrue(errs, "плоският формат ТРЯБВА да се отхвърля "
                              "(zen го приема мълчаливо и връща [])")
        # пълна диагностика: и липсващият inputNode, и липсващите edges
        self.assertTrue(any("inputNode" in e for e in errs), errs)
        self.assertTrue(any("edges" in e for e in errs), errs)

    def test_edge_to_missing_node_rejected(self):
        g = _full_graph()
        g["edges"][1]["targetId"] = "ghost"
        errs = validate_graph(g)
        self.assertTrue(any("ghost" in e for e in errs))

    def test_disconnected_table_rejected(self):
        g = _full_graph()
        g["edges"] = [{"id": "e1", "sourceId": "in1", "targetId": "out1"}]
        errs = validate_graph(g)
        self.assertTrue(any("disconnected" in e for e in errs))

    def test_empty_rules_allowed_ui_create_flow(self):
        # празна таблица (0 rules) НЕ е тиха отрова — UI "Create Table"
        # започва от нула; блокират се само структурните дефекти.
        g = _full_graph()
        g["nodes"][1]["content"]["rules"] = []
        self.assertEqual(validate_graph(g), [])

    def test_rules_without_columns_rejected(self):
        g = _full_graph()
        g["nodes"][1]["content"]["inputs"] = []
        errs = validate_graph(g)
        self.assertTrue(any("inputs" in e for e in errs), errs)

    def test_bad_json_string(self):
        self.assertEqual(validate_graph("{not json"), ["not valid JSON"])


class TestNormalizeGraph(BaseCase):

    def test_flat_wrapped_to_full(self):
        norm = normalize_jdm_graph(_flat_legacy())
        types = [n["type"] for n in norm["nodes"]]
        self.assertEqual(
            types, ["inputNode", "decisionTableNode", "outputNode"])
        self.assertEqual(len(norm["edges"]), 2)
        # нормализираният минава валидация
        self.assertEqual(validate_graph(norm), [])
        # rules получават _id; колоните получават field
        dt = norm["nodes"][1]["content"]
        self.assertTrue(all(r.get("_id") for r in dt["rules"]))
        self.assertTrue(all(c.get("field") for c in dt["inputs"]))

    def test_full_graph_untouched(self):
        g = _full_graph()
        self.assertEqual(normalize_jdm_graph(g), g)

    def test_unknown_format_untouched(self):
        weird = {"nodes": [{"id": "a", "type": "customNode"},
                           {"id": "b", "type": "decisionTableNode"}]}
        self.assertEqual(normalize_jdm_graph(weird), weird)

    def test_falsy_untouched(self):
        self.assertFalse(normalize_jdm_graph(False))
        self.assertIsNone(normalize_jdm_graph(None))
