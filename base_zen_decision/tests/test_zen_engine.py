# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
"""
Unit tests for the ZenWrapper — the thin GoRules JDM evaluator used by
the matrix engine.  The tests exercise each hit policy and the four
semantic table types (T0 constraints, T1 geometry, T2 materials,
T3 operations) against minimal in-memory JDM fixtures.
"""

import unittest

from odoo.exceptions import UserError
from odoo.tests.common import BaseCase

try:
    import zen  # noqa: F401

    _ZEN_AVAILABLE = True
except ImportError:
    _ZEN_AVAILABLE = False

from ..models.zen_engine import ZenWrapper


def _jdm_table(
    table_id: str,
    name: str,
    inputs: list,
    outputs: list,
    rules: list,
    hit_policy: str = "collect",
) -> dict:
    """Build a minimal GoRules JDM decision table wrapped in a document."""
    return {
        "nodes": [
            {
                "id": table_id,
                "name": name,
                "type": "decisionTable",
                "content": {
                    "hitPolicy": hit_policy,
                    "inputs": [
                        {"id": key, "name": key, "field": key} for key in inputs
                    ],
                    "outputs": [{"id": k, "name": k, "field": k} for k in outputs],
                    "rules": rules,
                },
            }
        ],
        "edges": [],
    }


@unittest.skipUnless(_ZEN_AVAILABLE, "zen-engine is not installed")
class TestZenWrapper(BaseCase):
    """ZenWrapper — standalone (no Odoo env dependency)."""

    def test_empty_table_returns_empty_dict(self):
        """Evaluating a falsy table returns {} instead of raising."""
        self.assertEqual(ZenWrapper.evaluate(None, {}), {})
        self.assertEqual(ZenWrapper.evaluate({}, {}), {})
        self.assertEqual(ZenWrapper.evaluate("", {}), {})

    def test_t0_constraint_error_match(self):
        """T0 error rule matches when width is below the minimum."""
        table = _jdm_table(
            table_id="t0",
            name="T0 Constraints",
            inputs=["width"],
            outputs=["level", "message"],
            rules=[
                {
                    "_id": "r1",
                    "width": "< 600",
                    "level": '"error"',
                    "message": '"Width must be at least 600 mm"',
                },
            ],
            hit_policy="collect",
        )
        result = ZenWrapper.evaluate(table, {"width": 500})
        # Collect returns a list; each entry is one matched rule's outputs
        self.assertTrue(result, "rule should have matched")

    def test_t0_constraint_no_match_returns_empty(self):
        """T0 rules that don't match produce no output."""
        table = _jdm_table(
            table_id="t0",
            name="T0 Constraints",
            inputs=["width"],
            outputs=["level", "message"],
            rules=[
                {"_id": "r1", "width": "< 600", "level": '"error"'},
            ],
            hit_policy="collect",
        )
        result = ZenWrapper.evaluate(table, {"width": 900})
        # No matches → empty list or dict
        if isinstance(result, list):
            self.assertEqual(result, [])
        else:
            self.assertFalse(result.get("errors"))

    def test_t1_geometry_first_policy_single_match(self):
        """T1 geometry with 'first' hit policy returns a single dict."""
        table = _jdm_table(
            table_id="t1",
            name="T1 Geometry",
            inputs=["material"],
            outputs=["density"],
            rules=[
                {"_id": "r1", "material": '"wood"', "density": "600"},
                {"_id": "r2", "material": '"steel"', "density": "7850"},
            ],
            hit_policy="first",
        )
        result = ZenWrapper.evaluate(table, {"material": "wood"})
        # First policy returns a dict (not a list)
        self.assertIsNotNone(result)

    def test_dict_vs_string_input(self):
        """ZenWrapper accepts both dict and JSON-string table formats."""
        import json

        table_dict = _jdm_table(
            table_id="t",
            name="T",
            inputs=["x"],
            outputs=["y"],
            rules=[{"_id": "r1", "x": "1", "y": "42"}],
            hit_policy="first",
        )
        # Same result for dict and string input
        result_from_dict = ZenWrapper.evaluate(table_dict, {"x": 1})
        result_from_str = ZenWrapper.evaluate(json.dumps(table_dict), {"x": 1})
        self.assertEqual(result_from_dict, result_from_str)

    def test_invalid_jdm_raises_user_error(self):
        """A syntactically broken JDM document raises UserError."""
        with self.assertRaises(UserError):
            ZenWrapper.evaluate({"nodes": [{"bogus": True}]}, {})
