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
- No lot_producing_ids → engine is a no-op
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
        operation_table=None,
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
                "operation_table": operation_table,
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
                "lot_producing_ids": [(4, lot.id)],
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

    # ── T3 operations: маршрутът е канонът, T3 допълва ────────────────

    def _wc(self, code):
        return self.env["mrp.workcenter"].create({"name": code, "code": code})

    def _t3_bom(self, *codes):
        """BoM с T3, който връща по един ред за всеки подаден код на център.

        🚨 Условието е върху ``width``, а НЕ върху ``material``, при все че
        останалите тестове тук ползват ``material``. Измерено на 31.08.2026:
        ``_get_design_context`` връща ключ **``Material``** (полето ``string``),
        не ``material`` (полето ``name``) — параметър без ``param_dictionary``
        стига до таблиците само под етикета си. Правило с вход ``material``
        НИКОГА не се задейства, T3 връща нула реда, и тогава тестът за дедупа
        минава, защото няма какво да се дублира — тоест не доказва нищо.
        ``width`` е измерено налично в контекста. Въпросът дали контекстът или
        заварените тестове са сгрешени е ОТДЕЛЕН и стои отворен (ADR-0010).
        """
        return self._build_bom(
            operation_table=_jdm(
                inputs=["width"],
                outputs=["workcenter_code", "duration_min"],
                rules=[
                    {
                        "_id": "r%d" % i,
                        "width": ">= 0",
                        "workcenter_code": '"%s"' % code,
                        "duration_min": "10",
                    }
                    for i, code in enumerate(codes, start=1)
                ],
            ),
        )

    def _routing_wo(self, mo, workcenter):
        """Имитира workorder-а, който native Odoo ражда от реда на маршрута.

        Ключовото е ``operation_id``: по него се различава маршрутният
        workorder от T3-ния.
        """
        operation = self.env["mrp.routing.workcenter"].create(
            {
                "name": "Routing %s" % workcenter.code,
                "bom_id": mo.bom_id.id,
                "workcenter_id": workcenter.id,
                "time_cycle_manual": 42.0,
            }
        )
        return self.env["mrp.workorder"].create(
            {
                "name": operation.name,
                "production_id": mo.id,
                "workcenter_id": workcenter.id,
                "operation_id": operation.id,
                "product_uom_id": mo.product_uom_id.id,
                "duration_expected": 42.0,
            }
        )

    def test_t3_skips_workcenter_already_covered_by_routing(self):
        """T3 НЕ ражда втори workorder за център, който маршрутът покрива.

        Регресията: СПЦС/MO/00555 получи 9 workorder-а от BoM с 5 операции,
        защото двата пътя минаваха без дедуп и трудът се удвои.
        """
        wc = self._wc("SDMETAL")
        bom = self._t3_bom("SDMETAL")
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})
        self._routing_wo(mo, wc)

        mo._generate_design_matrix_moves()

        na_centara = mo.workorder_ids.filtered(lambda w: w.workcenter_id == wc)
        self.assertEqual(
            len(na_centara),
            1,
            "routing already covers SDMETAL — T3 must not add a second workorder",
        )
        self.assertTrue(
            na_centara.operation_id,
            "the surviving workorder must be the routing one, not the T3 one",
        )
        self.assertEqual(
            sum(mo.workorder_ids.mapped("duration_expected")),
            42.0,
            "labour must not double",
        )

    def test_t3_still_creates_for_workcenter_outside_the_routing(self):
        """Контролата: T3 ДОПЪЛВА там, където маршрутът мълчи.

        Без този тест поправката би минала и ако T3 беше изключено изцяло.
        """
        pokrit = self._wc("SDMETAL")
        nepokrit = self._wc("SDQC")
        bom = self._t3_bom("SDMETAL", "SDQC")
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})
        self._routing_wo(mo, pokrit)

        mo._generate_design_matrix_moves()

        self.assertEqual(
            len(mo.workorder_ids.filtered(lambda w: w.workcenter_id == pokrit)),
            1,
            "covered workcenter stays at one workorder",
        )
        ot_t3 = mo.workorder_ids.filtered(lambda w: w.workcenter_id == nepokrit)
        self.assertEqual(
            len(ot_t3), 1, "T3 must still create for an uncovered workcenter"
        )
        self.assertFalse(
            ot_t3.operation_id, "a T3 workorder carries no routing operation"
        )

    def test_t3_creates_both_when_there_is_no_routing_at_all(self):
        """BoM без маршрут → T3 е единственият източник, нищо не се губи."""
        self._wc("SDMETAL")
        self._wc("SDQC")
        bom = self._t3_bom("SDMETAL", "SDQC")
        mo, _ = self._build_mo_with_lot(bom, {"material": "wood"})

        mo._generate_design_matrix_moves()

        self.assertEqual(
            len(mo.workorder_ids), 2, "with no routing, both T3 rows must land"
        )

    # ── Safety nets ───────────────────────────────────────────────────

    def test_no_lot_producing_is_noop(self):
        """MO without lot_producing_ids → engine logs and returns quietly."""
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
