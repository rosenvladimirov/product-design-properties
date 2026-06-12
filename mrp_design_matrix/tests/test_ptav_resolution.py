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
Tests for ``MrpProduction._resolve_variant_by_ptav``.

PTAV resolution is the T2 Type-3 row behaviour: the matrix returns a
``product_tmpl_ref`` + ``param_attribute_map`` dict and the engine
walks the template's product.template.attribute.value (PTAV) records
to find a matching variant.

The tests build a real product template with two attributes (material
and size) and three variants, then exercise the resolution logic end
to end.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPtavResolution(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Template = cls.env["product.template"]
        cls.Production = cls.env["mrp.production"]

        # Two attributes: material (wood / steel) and finish (matte / glossy)
        cls.attr_material = cls.Attribute.create(
            {
                "name": "Test Material",
                "create_variant": "always",
                "sequence": 10,
            }
        )
        cls.val_wood = cls.AttributeValue.create(
            {"name": "wood", "attribute_id": cls.attr_material.id}
        )
        cls.val_steel = cls.AttributeValue.create(
            {"name": "steel", "attribute_id": cls.attr_material.id}
        )

        cls.attr_finish = cls.Attribute.create(
            {
                "name": "Test Finish",
                "create_variant": "always",
                "sequence": 20,
            }
        )
        cls.val_matte = cls.AttributeValue.create(
            {"name": "matte", "attribute_id": cls.attr_finish.id}
        )
        cls.val_glossy = cls.AttributeValue.create(
            {"name": "glossy", "attribute_id": cls.attr_finish.id}
        )

        # Template with both attribute lines — 4 variants generated
        cls.tmpl = cls.Template.create(
            {
                "name": "PTAV Test Product",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attr_material.id,
                            "value_ids": [(6, 0, [cls.val_wood.id, cls.val_steel.id])],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attr_finish.id,
                            "value_ids": [
                                (6, 0, [cls.val_matte.id, cls.val_glossy.id])
                            ],
                        },
                    ),
                ],
            }
        )

        # Create an external-ID-free dummy MO for method invocation
        cls.finished = cls.env["product.product"].create(
            {"name": "PTAV Finished Dummy", "is_storable": True}
        )
        cls.mo = cls.Production.new(
            {
                "product_id": cls.finished.id,
                "product_qty": 1.0,
                "product_uom_id": cls.finished.uom_id.id,
            }
        )

    def _xmlid_for(self, record):
        """Return an xmlid for an env-ref-friendly parameter.  Creates one
        in ``__test__.*`` namespace if none exists."""
        existing = self.env["ir.model.data"].search(
            [("model", "=", record._name), ("res_id", "=", record.id)],
            limit=1,
        )
        if existing:
            return f"{existing.module}.{existing.name}"
        data = self.env["ir.model.data"].create(
            {
                "name": f"test_ptav_{record._name}_{record.id}",
                "module": "__test__",
                "model": record._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
        return f"{data.module}.{data.name}"

    # ── Resolution scenarios ─────────────────────────────────────────

    def test_resolve_single_attribute(self):
        """Match by one attribute → returns the correct variant."""
        mat_ref = self._xmlid_for(self.attr_material)
        # Pick any one of the matte-finish variants for a sanity check
        result = self.mo._resolve_variant_by_ptav(
            self.tmpl,
            {"material": mat_ref},
            {"material": "wood"},
        )
        self.assertTrue(result, "should resolve a variant")
        # The returned variant must include the 'wood' PTAV
        ptav_names = result.product_template_variant_value_ids.mapped("name")
        self.assertIn("wood", ptav_names)

    def test_resolve_two_attributes(self):
        """Match by two attributes → returns the exact variant."""
        mat_ref = self._xmlid_for(self.attr_material)
        finish_ref = self._xmlid_for(self.attr_finish)
        result = self.mo._resolve_variant_by_ptav(
            self.tmpl,
            {"material": mat_ref, "finish": finish_ref},
            {"material": "steel", "finish": "glossy"},
        )
        self.assertTrue(result)
        ptav_names = set(result.product_template_variant_value_ids.mapped("name"))
        self.assertEqual(ptav_names, {"steel", "glossy"})

    def test_resolve_no_match_returns_false(self):
        """Value that has no matching PTAV yields False."""
        mat_ref = self._xmlid_for(self.attr_material)
        result = self.mo._resolve_variant_by_ptav(
            self.tmpl,
            {"material": mat_ref},
            {"material": "titanium"},  # not a defined value
        )
        self.assertFalse(result)

    def test_resolve_empty_context_returns_false(self):
        """Empty or missing design context values → no needed PTAVs → False."""
        mat_ref = self._xmlid_for(self.attr_material)
        result = self.mo._resolve_variant_by_ptav(
            self.tmpl,
            {"material": mat_ref},
            {},  # no material in context
        )
        self.assertFalse(result)

    def test_resolve_invalid_attr_ref_skipped(self):
        """Unknown attribute external-id is skipped with a warning."""
        finish_ref = self._xmlid_for(self.attr_finish)
        result = self.mo._resolve_variant_by_ptav(
            self.tmpl,
            {
                "material": "bogus.ref.that.does.not.exist",
                "finish": finish_ref,
            },
            {"material": "wood", "finish": "matte"},
        )
        # Bogus attr is skipped; finish still resolves a variant
        self.assertTrue(result)
        ptav_names = set(result.product_template_variant_value_ids.mapped("name"))
        self.assertIn("matte", ptav_names)
