# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
Integration tests for ``sale.order.line`` design-lot handling.

Covers:

- ``has_design_definition`` detection via the product (direct link)
- ``has_design_definition`` detection via the BoM (fallback)
- ``design_param_definition_id`` filtered by company active definitions
- ``set_design_lot`` RPC writes the lot on the line
- ``_prepare_procurement_values`` includes ``design_lot_id``
- ``get_design_definition_for_product`` RPC response shape
- ``design_params_summary`` reflects the lot's Properties
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleLineDesignLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Bom = cls.env["mrp.bom"]
        cls.Lot = cls.env["stock.lot"]
        cls.Definition = cls.env["design.param.definition"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.Partner = cls.env["res.partner"]

        cls.partner = cls.Partner.create({"name": "Test Customer"})

        cls.definition = cls.Definition.create(
            {
                "code": "sale_test_def",
                "name": "Sale Test Definition",
                "design_params_definition": [
                    {
                        "name": "width",
                        "type": "float",
                        "string": "Width (mm)",
                        "default": "900",
                    },
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "default": "wood",
                        "selection": [["wood", "Wood"], ["steel", "Steel"]],
                    },
                ],
            }
        )

        # Plain product (no design definition)
        cls.plain = cls.Product.create({"name": "Plain Product", "is_storable": True})

        # Product with a BoM that carries the design definition
        cls.bom_product = cls.Product.create(
            {"name": "BoM Design Product", "is_storable": True, "tracking": "lot"}
        )
        cls.bom = cls.Bom.create(
            {
                "product_tmpl_id": cls.bom_product.product_tmpl_id.id,
                "product_qty": 1.0,
                "design_param_definition_id": cls.definition.id,
            }
        )

        # Product with a direct definition link (no BoM required)
        cls.direct_product = cls.Product.create(
            {
                "name": "Direct Design Product",
                "is_storable": True,
                "tracking": "lot",
                "design_param_definition_id": cls.definition.id,
            }
        )

    def _make_so_line(self, product):
        so = self.SaleOrder.create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1.0,
                        },
                    )
                ],
            }
        )
        return so.order_line[0]

    def _make_lot(self, product, **params):
        serial = self.env["ir.sequence"].next_by_code("stock.lot.serial") or "X"
        return self.Lot.create(
            {
                "name": f"TEST-SALE-LOT-{serial}",
                "product_id": product.id,
                "design_param_definition_id": self.definition.id,
                "design_params": params or False,
            }
        )

    # ── has_design_definition computation ────────────────────────────

    def test_plain_product_has_no_design_definition(self):
        """A product without BoM or direct link returns False."""
        line = self._make_so_line(self.plain)
        self.assertFalse(line.has_design_definition)
        self.assertFalse(line.design_param_definition_id)

    def test_bom_product_has_design_definition_via_bom(self):
        """Definition resolved through the BoM fallback."""
        line = self._make_so_line(self.bom_product)
        self.assertTrue(line.has_design_definition)
        self.assertEqual(line.design_param_definition_id, self.definition)

    def test_direct_product_has_design_definition(self):
        """Definition resolved directly on product.product."""
        line = self._make_so_line(self.direct_product)
        self.assertTrue(line.has_design_definition)
        self.assertEqual(line.design_param_definition_id, self.definition)

    def test_company_active_definitions_filter(self):
        """Non-empty active definitions that exclude this one → False."""
        # Create a second definition and restrict the company to only it
        other_def = self.Definition.create({"code": "other_def", "name": "Other"})
        self.env.company.design_definition_ids = [(6, 0, [other_def.id])]
        # Re-create line to recompute
        line = self._make_so_line(self.direct_product)
        self.assertFalse(line.has_design_definition)
        # Reset for follow-up tests
        self.env.company.design_definition_ids = [(5, 0, 0)]

    # ── set_design_lot / design_params_summary ───────────────────────

    def test_set_design_lot_rpc(self):
        """``set_design_lot`` writes the lot on the line."""
        line = self._make_so_line(self.bom_product)
        lot = self._make_lot(self.bom_product, material="wood")
        line.set_design_lot(lot.id)
        self.assertEqual(line.design_lot_id, lot)

    def test_design_params_summary(self):
        """Summary joins design_params into a human-readable string."""
        line = self._make_so_line(self.bom_product)
        lot = self._make_lot(self.bom_product, material="wood")
        line.design_lot_id = lot
        # Summary should contain the material value
        self.assertIn("material", line.design_params_summary)
        self.assertIn("wood", line.design_params_summary)

    def test_design_params_summary_empty(self):
        """Summary is empty when lot has no design_params."""
        line = self._make_so_line(self.bom_product)
        lot = self._make_lot(self.bom_product)
        line.design_lot_id = lot
        self.assertEqual(line.design_params_summary or "", "")

    # ── Procurement propagation ──────────────────────────────────────

    def test_prepare_procurement_values_includes_lot(self):
        """``_prepare_procurement_values`` forwards ``design_lot_id``."""
        line = self._make_so_line(self.bom_product)
        lot = self._make_lot(self.bom_product, material="steel")
        line.design_lot_id = lot
        vals = line._prepare_procurement_values()
        self.assertEqual(vals.get("design_lot_id"), lot.id)

    def test_prepare_procurement_values_without_lot(self):
        """Without a design lot, the key is absent from procurement values."""
        line = self._make_so_line(self.bom_product)
        vals = line._prepare_procurement_values()
        self.assertNotIn("design_lot_id", vals)

    # ── get_design_definition_for_product RPC ────────────────────────

    def test_get_design_definition_for_product_direct(self):
        """RPC resolves the definition directly from the product."""
        result = self.env["sale.order.line"].get_design_definition_for_product(
            self.direct_product.id
        )
        self.assertTrue(result)
        self.assertEqual(result["definitionId"], self.definition.id)
        self.assertEqual(result["definitionCode"], "sale_test_def")

    def test_get_design_definition_for_product_via_bom(self):
        """RPC falls back to the BoM when product has no direct link."""
        result = self.env["sale.order.line"].get_design_definition_for_product(
            self.bom_product.id
        )
        self.assertTrue(result)
        self.assertEqual(result["definitionId"], self.definition.id)

    def test_get_design_definition_for_product_none(self):
        """RPC returns False for plain products."""
        result = self.env["sale.order.line"].get_design_definition_for_product(
            self.plain.id
        )
        self.assertFalse(result)

    def test_onchange_product_resets_design_lot(self):
        """Changing the product clears any existing design lot."""
        line = self._make_so_line(self.bom_product)
        lot = self._make_lot(self.bom_product, material="wood")
        line.design_lot_id = lot
        self.assertEqual(line.design_lot_id, lot)
        line.product_id = self.plain
        line._onchange_product_id_reset_design_lot()
        self.assertFalse(line.design_lot_id)
