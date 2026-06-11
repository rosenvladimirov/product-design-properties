# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
Integration tests for ``MrpProduction._generate_design_matrix_moves``.

Builds a minimal BoM with constraint / geometry / material tables in
memory, creates a lot with design parameters, runs the engine, and
verifies that the resulting raw moves match expectations.

Each test covers a distinct code path:

- T0 error → UserError raised
- T0 warning → message_post called, execution continues
- BoM line with coeff_default=0 stays inactive
- BoM line with coeff_default>0 generates a move
- T2 material coefficient lookup via matrix_coeff_rule
- No lot_producing_id → engine is a no-op
"""

import unittest

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

try:
    import zen  # noqa: F401

    _ZEN_AVAILABLE = True
except ImportError:
    _ZEN_AVAILABLE = False


def _jdm(inputs, outputs, rules, hit_policy="collect", name="Table"):
    return {
        "nodes": [
            {
                "id": "t",
                "name": name,
                "type": "decisionTable",
                "content": {
                    "hitPolicy": hit_policy,
                    "inputs": [{"id": k, "name": k, "field": k} for k in inputs],
                    "outputs": [{"id": k, "name": k, "field": k} for k in outputs],
                    "rules": rules,
                },
            }
        ],
        "edges": [],
    }


@unittest.skipUnless(_ZEN_AVAILABLE, "zen-engine is not installed")
@tagged("post_install", "-at_install")
class TestMatrixMoves(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.BomLine = cls.env["mrp.bom.line"]
        cls.Production = cls.env["mrp.production"]
        cls.Lot = cls.env["stock.lot"]
        cls.Definition = cls.env["design.param.definition"]

        # Finished product
        cls.finished = cls.Product.create(
            {
                "name": "Test Door",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        # Components
        cls.slab = cls.Product.create({"name": "Wood Slab", "is_storable": True})
        cls.hinges = cls.Product.create({"name": "Hinge Set", "is_storable": True})
        cls.glass = cls.Product.create({"name": "Glass Panel", "is_storable": True})

        cls.definition = cls.Definition.create(
            {
                "code": "test_door_def",
                "name": "Test Door Def",
                "design_params_definition": [
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "default": "wood",
                        "selection": [["wood", "Wood"], ["glass", "Glass"]],
                    },
                ],
            }
        )

    def _build_bom(
        self,
        constraint_table=None,
        geometry_table=None,
        material_table=None,
        lines=None,
    ):
        """Create a BoM with the given tables and lines."""
        bom = self.Bom.create(
            {
                "product_tmpl_id": self.finished.product_tmpl_id.id,
                "product_qty": 1.0,
                "design_param_definition_id": self.definition.id,
                "constraint_table": constraint_table,
                "geometry_table": geometry_table,
                "material_table": material_table,
            }
        )
        for line_vals in lines or []:
            self.BomLine.create({"bom_id": bom.id, **line_vals})
        return bom

    def _build_mo_with_lot(self, bom, design_params):
        """Create an MO with a lot that carries the given design params."""
        serial = self.env["ir.sequence"].next_by_code("stock.lot.serial") or "X"
        lot = self.Lot.create(
            {
                "name": f"TEST-LOT-{serial}",
                "product_id": self.finished.id,
                "design_param_definition_id": self.definition.id,
                "design_params": design_params,
            }
        )
        mo = self.Production.create(
            {
                "product_id": self.finished.id,
                "product_qty": 1.0,
                "product_uom_id": self.finished.uom_id.id,
                "bom_id": bom.id,
                "lot_producing_id": lot.id,
            }
        )
        return mo, lot

    # ── T0 constraints ────────────────────────────────────────────────

    def test_t0_error_raises_user_error(self):
        """A T0 error rule that matches raises UserError."""
        t0 = _jdm(
            inputs=["material"],
            outputs=["errors"],
            rules=[
                {
                    "_id": "r1",
                    "material": '"glass"',
                    "errors": '[{"message": "glass not supported"}]',
                },
            ],
        )
        bom = self._build_bom(constraint_table=t0)
        mo, _ = self._build_mo_with_lot(bom, {"material": "glass"})
        with self.assertRaises(UserError):
            mo._generate_design_matrix_moves()

    def test_t0_passes_when_no_rule_matches(self):
        """No matching T0 rule → no error, engine proceeds."""
        t0 = _jdm(
            inputs=["material"],
            outputs=["errors"],
            rules=[
                {
                    "_id": "r1",
                    "material": '"glass"',
                    "errors": '[{"message": "glass not supported"}]',
                },
            ],
        )
        bom = self._build_bom(constraint_table=t0)
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})
        # Should not raise
        mo._generate_design_matrix_moves()

    # ── BoM line generation ───────────────────────────────────────────

    def test_bom_line_always_used(self):
        """coeff_default > 0 → move is created."""
        bom = self._build_bom(
            constraint_table=_jdm(["material"], ["x"], []),
            lines=[
                {
                    "product_id": self.slab.id,
                    "product_qty": 1.0,
                    "coeff_default": 1.0,
                }
            ],
        )
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})
        mo._generate_design_matrix_moves()
        slab_moves = mo.move_raw_ids.filtered(lambda m: m.product_id == self.slab)
        self.assertTrue(slab_moves, "slab move should have been created")

    def test_bom_line_o_variant_skipped(self):
        """coeff_default = 0 and no matrix rule → no move."""
        bom = self._build_bom(
            constraint_table=_jdm(["material"], ["x"], []),
            lines=[
                {
                    "product_id": self.glass.id,
                    "product_qty": 1.0,
                    "coeff_default": 0.0,
                    "matrix_coeff_rule": "glass_coeff",
                }
            ],
        )
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})
        mo._generate_design_matrix_moves()
        glass_moves = mo.move_raw_ids.filtered(lambda m: m.product_id == self.glass)
        self.assertFalse(
            glass_moves, "O-variant with no matrix match should stay inactive"
        )

    def test_matrix_coeff_cached_lookup(self):
        """_eval_matrix_coeff_cached returns the value from the dict."""
        bom = self._build_bom(
            constraint_table=_jdm(["material"], ["x"], []),
            lines=[
                {
                    "product_id": self.glass.id,
                    "product_qty": 1.0,
                    "coeff_default": 0.0,
                    "matrix_coeff_rule": "glass_coeff",
                }
            ],
        )
        mo, _ = self._build_mo_with_lot(bom, {"material": "glass"})
        line = bom.bom_line_ids[0]
        # Match → returns matrix coeff
        self.assertEqual(
            mo._eval_matrix_coeff_cached(line, {"glass_coeff": 2.5}),
            2.5,
        )
        # No match → falls back to coeff_default
        self.assertEqual(
            mo._eval_matrix_coeff_cached(line, {"other_key": 5.0}),
            0.0,
        )

    def test_bom_line_o_variant_activated_by_matrix(self):
        """T2 material table activates an O-variant via matrix_coeff_rule."""
        t2 = _jdm(
            inputs=["material"],
            outputs=["glass_coeff", "bom_line_coeff_key"],
            rules=[
                {
                    "_id": "r1",
                    "material": '"glass"',
                    "glass_coeff": "1.0",
                    "bom_line_coeff_key": '"glass_coeff"',
                },
            ],
        )
        bom = self._build_bom(
            constraint_table=_jdm(["material"], ["x"], []),
            material_table=t2,
            lines=[
                {
                    "product_id": self.glass.id,
                    "product_qty": 2.0,
                    "coeff_default": 0.0,
                    "matrix_coeff_rule": "glass_coeff",
                }
            ],
        )
        mo, _ = self._build_mo_with_lot(bom, {"material": "glass"})
        mo._generate_design_matrix_moves()
        glass_moves = mo.move_raw_ids.filtered(lambda m: m.product_id == self.glass)
        self.assertTrue(
            glass_moves,
            "O-variant should activate when matrix returns a non-zero coeff",
        )

    # ── Safety nets ───────────────────────────────────────────────────

    def test_no_lot_producing_is_noop(self):
        """MO without lot_producing_id → engine logs and returns quietly."""
        bom = self._build_bom(
            constraint_table=_jdm(["material"], ["x"], []),
            lines=[
                {
                    "product_id": self.slab.id,
                    "product_qty": 1.0,
                    "coeff_default": 1.0,
                }
            ],
        )
        mo = self.Production.create(
            {
                "product_id": self.finished.id,
                "product_qty": 1.0,
                "product_uom_id": self.finished.uom_id.id,
                "bom_id": bom.id,
            }
        )
        # Should not raise even without a lot
        mo._generate_design_matrix_moves()
