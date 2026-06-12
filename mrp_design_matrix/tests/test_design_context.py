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
"""
Tests for ``stock.lot._get_design_context`` and the child-lot helpers.
These do not require the GoRules engine — they exercise the pure-Python
context-building logic used by ``_generate_design_matrix_moves``.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDesignContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Definition = cls.env["design.param.definition"]
        cls.Lot = cls.env["stock.lot"]
        cls.Product = cls.env["product.product"]

        cls.product = cls.Product.create(
            {
                "name": "Test Design Product",
                "is_storable": True,
                "tracking": "lot",
            }
        )

        cls.definition = cls.Definition.create(
            {
                "code": "test_def",
                "name": "Test Definition",
                "design_params_definition": [
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "default": "wood",
                        "selection": [["wood", "Wood"], ["steel", "Steel"]],
                    },
                    {
                        "name": "leaf_type",
                        "type": "selection",
                        "string": "Leaf Type",
                        "default": "single",
                        "selection": [["single", "Single"], ["double", "Double"]],
                    },
                ],
            }
        )

    def _make_lot(self, **params):
        """Create a stock.lot with the test definition + given design params."""
        serial = self.env["ir.sequence"].next_by_code("stock.lot.serial") or "X"
        return self.Lot.create(
            {
                "name": f"TEST-LOT-{serial}",
                "product_id": self.product.id,
                "design_param_definition_id": self.definition.id,
                "design_params": params or False,
            }
        )

    # ── _get_design_context ──────────────────────────────────────────

    def test_design_context_merges_dims_and_params(self):
        """Context merges width/height/thickness + design_params keys."""
        lot = self._make_lot(material="wood", leaf_type="single")
        ctx = lot._get_design_context()
        # Dimensions always present (default 0.0 if _dim module absent)
        self.assertIn("width", ctx)
        self.assertIn("height", ctx)
        self.assertIn("thickness", ctx)
        # Design params flattened
        self.assertEqual(ctx["material"], "wood")
        self.assertEqual(ctx["leaf_type"], "single")

    def test_design_context_empty_params(self):
        """Lot without design_params still returns dim keys."""
        lot = self._make_lot()
        ctx = lot._get_design_context()
        self.assertEqual(ctx["width"], 0.0)
        self.assertEqual(ctx["height"], 0.0)
        # No design_params → only dim keys
        self.assertNotIn("material", ctx)

    # ── _find_matching_stock_lot ────────────────────────────────────

    def test_find_matching_lot_exact(self):
        """Finds a lot whose design_params match all required keys."""
        lot_a = self._make_lot(material="wood", leaf_type="single")
        lot_b = self._make_lot(material="steel", leaf_type="double")

        found = self.Lot._find_matching_stock_lot(self.product, {"material": "wood"})
        self.assertEqual(found, lot_a)

        found = self.Lot._find_matching_stock_lot(self.product, {"leaf_type": "double"})
        self.assertEqual(found, lot_b)

    def test_find_matching_lot_no_match(self):
        """Returns empty recordset when no lot matches."""
        self._make_lot(material="wood")
        found = self.Lot._find_matching_stock_lot(
            self.product, {"material": "titanium"}
        )
        self.assertFalse(found)

    def test_find_matching_lot_ignores_extra_params(self):
        """Extra lot params do not break the match."""
        lot = self._make_lot(material="wood", leaf_type="single")
        found = self.Lot._find_matching_stock_lot(self.product, {"material": "wood"})
        self.assertEqual(found, lot)

    # ── _create_child_lot ───────────────────────────────────────────

    def test_create_child_lot_direct_copy(self):
        """Direct copy: child key maps to exact parent ctx key."""
        parent = self._make_lot(material="wood", leaf_type="single")
        # Create a BoM line stub with param_extraction_map
        fake_bom_line = self.env["mrp.bom.line"].new(
            {
                "param_extraction_map": {
                    "child_material": "material",
                },
                "child_definition_id": self.definition.id,
            }
        )
        child = self.Lot._create_child_lot(parent, fake_bom_line, self.product)
        self.assertEqual(child.design_params.get("child_material"), "wood")

    def test_create_child_lot_safe_eval_expression(self):
        """Unknown keys are treated as safe_eval expressions on parent ctx."""
        parent = self._make_lot(material="wood", leaf_type="single")
        fake_bom_line = self.env["mrp.bom.line"].new(
            {
                "param_extraction_map": {
                    # "upper_material" is not a parent key, so it's eval'd
                    "upper_material": "material.upper()",
                },
                "child_definition_id": self.definition.id,
            }
        )
        child = self.Lot._create_child_lot(parent, fake_bom_line, self.product)
        self.assertEqual(child.design_params.get("upper_material"), "WOOD")
