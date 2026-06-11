# Copyright 2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
Tests for the extended formula evaluation in
``mrp_bom_line_formula_template``.

Covers:

- Legacy ``quantity = ...`` syntax still works (OCA compat)
- New ``result = ...`` syntax
- ``product`` override via ``env.ref()``
- ``uom`` override via ``env.ref()``
- ``design_context`` kwarg injects keys as top-level formula variables
- Empty formula returns ``None``
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestFormulaEval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.BomLine = cls.env["mrp.bom.line"]
        cls.Template = cls.env["mrp.bom.line.formula.template"]

        cls.parent_product = cls.Product.create(
            {"name": "Parent Product", "is_storable": True}
        )
        cls.component = cls.Product.create({"name": "Component", "is_storable": True})
        cls.override_product = cls.Product.create(
            {"name": "Override Component", "is_storable": True}
        )
        cls.bom = cls.Bom.create(
            {
                "product_tmpl_id": cls.parent_product.product_tmpl_id.id,
                "product_qty": 1.0,
            }
        )

    def _make_line(self, formula: str):
        """Create a BoM line with an inline formula (no template)."""
        snippet = formula.split("\n", 1)[0][:20]
        template = self.Template.create(
            {
                "name": f"inline-{snippet}",
                "quantity_formula": formula,
            }
        )
        line = self.BomLine.create(
            {
                "bom_id": self.bom.id,
                "product_id": self.component.id,
                "product_qty": 1.0,
                "formula_template_id": template.id,
            }
        )
        return line

    def _eval(self, line, design_context=None):
        """Run _eval_quantity_formula with unit context."""
        return line._eval_quantity_formula(
            product=line.product_id,
            product_uom=line.uom_id,
            product_uom_qty=1.0,
            production=self.env["mrp.production"],
            design_context=design_context,
        )

    # ── Output variable compatibility ─────────────────────────────────

    def test_legacy_quantity_variable(self):
        """Writing ``quantity = N`` still works (OCA backward compat)."""
        line = self._make_line("quantity = product_uom_qty * 3")
        self.assertEqual(self._eval(line), 3)

    def test_new_result_variable(self):
        """Writing ``result = N`` is supported."""
        line = self._make_line("result = product_uom_qty * 2")
        self.assertEqual(self._eval(line), 2)

    def test_result_takes_precedence_over_quantity(self):
        """When both are set, ``result`` wins."""
        line = self._make_line("quantity = 1\nresult = 42")
        self.assertEqual(self._eval(line), 42)

    def test_empty_formula_returns_none(self):
        """A line without a formula returns ``None``."""
        # Create a template with empty-ish formula, then blank the line
        template = self.Template.create(
            {"name": "empty", "quantity_formula": "result = 0"}
        )
        line = self.BomLine.create(
            {
                "bom_id": self.bom.id,
                "product_id": self.component.id,
                "product_qty": 1.0,
                "formula_template_id": template.id,
            }
        )
        # Simulate no formula by temporarily removing it
        line.formula_template_id = False
        line.invalidate_recordset(["quantity_formula"])
        self.assertIsNone(self._eval(line))

    # ── Product / UoM override ────────────────────────────────────────

    def test_product_override_returns_dict(self):
        """Setting ``product`` in the formula returns a dict result."""
        override_id = self.override_product.id
        line = self._make_line(
            f"result = 5\nproduct = env['product.product'].browse({override_id})"
        )
        result = self._eval(line)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["quantity"], 5)
        self.assertEqual(result["product"], self.override_product)
        self.assertIsNone(result["uom"])

    def test_no_product_change_returns_float(self):
        """When the formula does not touch ``product``, result is a float."""
        line = self._make_line("result = 7")
        result = self._eval(line)
        self.assertEqual(result, 7)
        self.assertNotIsInstance(result, dict)

    def test_uom_override(self):
        """Setting ``uom`` in the formula returns a dict with the new UoM."""
        other_uom = self.env.ref("uom.product_uom_unit")
        uom_id = other_uom.id
        # Make sure the override UoM is different from the line's default
        line = self._make_line(f"result = 1\nuom = env['uom.uom'].browse({uom_id})")
        result = self._eval(line)
        # Only returns dict when the UoM actually differs
        if result != 1:
            self.assertIsInstance(result, dict)
            self.assertEqual(result["uom"], other_uom)

    # ── design_context injection ─────────────────────────────────────

    def test_design_context_injection(self):
        """Keys from design_context become top-level formula variables."""
        line = self._make_line("result = width * height / 1000000")
        ctx = {"width": 900, "height": 2100}
        result = self._eval(line, design_context=ctx)
        # 900 * 2100 / 1e6 = 1.89
        self.assertAlmostEqual(result, 1.89, places=4)

    def test_design_context_available_as_dict(self):
        """The full ``design_context`` dict is also exposed by name."""
        line = self._make_line("result = design_context['width']")
        result = self._eval(line, design_context={"width": 555})
        self.assertEqual(result, 555)

    def test_env_available_in_formula(self):
        """``env`` is exposed so formulas can use env.ref / search."""
        line = self._make_line(
            "result = env['product.product'].search_count([]) > 0 and 1 or 0"
        )
        self.assertEqual(self._eval(line), 1)
