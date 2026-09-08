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
"""Tests for the lot prefix carried by the product design properties.

Odoo's own machinery is what produces the number — these tests assert the
bridge (property -> ``serial_prefix_format``) and then let the standard
``stock.lot`` compute prove the prefix actually reaches a lot name.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

PREFIX_UUID = "3f6c1d90ab1e4c02"


@tagged("post_install", "-at_install")
class TestDesignLotPrefix(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Definition = cls.env["design.param.definition"]
        cls.Product = cls.env["product.product"]
        cls.Template = cls.env["product.template"]
        cls.Lot = cls.env["stock.lot"]
        cls.Sequence = cls.env["ir.sequence"]

        # Дефиницията носи property от тип char, а param_dictionary го връзва
        # с каноничното име `lot_prefix` — точно както го прави XML вносът.
        cls.definition = cls.Definition.create(
            {
                "code": "test_lot_prefix",
                "name": "Test Lot Prefix",
                "design_params_definition": [
                    {
                        "name": PREFIX_UUID,
                        "type": "char",
                        "string": "Lot Prefix",
                    },
                ],
                "param_dictionary": {
                    "lot_prefix": {
                        "uuid": PREFIX_UUID,
                        "name": {"en_US": "Lot Prefix"},
                        "aliases": [],
                    },
                },
            }
        )
        cls.default_sequence = cls.env.ref(
            "stock.sequence_production_lots", raise_if_not_found=False
        )

    def _make_product(self, prefix=None, name="Design Door"):
        vals = {
            "name": name,
            "is_storable": True,
            "tracking": "lot",
            "design_param_definition_id": self.definition.id,
        }
        if prefix is not None:
            vals["design_properties"] = {PREFIX_UUID: prefix}
        return self.Product.create(vals)

    # ── the bridge ───────────────────────────────────────────────────

    def test_prefix_from_properties_reaches_the_template(self):
        product = self._make_product("Б")
        self.assertEqual(product._design_lot_prefix(), "Б")
        self.assertEqual(product.product_tmpl_id.serial_prefix_format, "Б")
        sequence = product.product_tmpl_id.lot_sequence_id
        self.assertEqual(sequence.prefix, "Б")
        self.assertNotEqual(sequence, self.default_sequence)

    def test_prefix_reaches_the_lot_name(self):
        """The name itself is Odoo's job — assert it carries the prefix."""
        product = self._make_product("ИС")
        lot = self.Lot.create({"product_id": product.id})
        self.assertTrue(
            lot.name.startswith("ИС"),
            f"lot name {lot.name!r} does not carry the prefix",
        )

    def test_same_prefix_reuses_one_sequence(self):
        first = self._make_product("Г", name="Garage A")
        second = self._make_product("Г", name="Garage B")
        self.assertEqual(
            first.product_tmpl_id.lot_sequence_id,
            second.product_tmpl_id.lot_sequence_id,
        )

    def test_write_moves_the_prefix(self):
        product = self._make_product("Б")
        product.write({"design_properties": {PREFIX_UUID: "МФ"}})
        self.assertEqual(product.product_tmpl_id.serial_prefix_format, "МФ")

    # ── the cases that must NOT renumber anything ────────────────────

    def test_no_property_leaves_the_default_sequence(self):
        product = self._make_product()
        self.assertEqual(product._design_lot_prefix(), "")
        self.assertEqual(product.product_tmpl_id.lot_sequence_id, self.default_sequence)

    def test_empty_property_leaves_the_default_sequence(self):
        """Празно property се чете като False — не бива да мине за префикс."""
        product = self._make_product("   ")
        self.assertEqual(product._design_lot_prefix(), "")
        self.assertEqual(product.product_tmpl_id.lot_sequence_id, self.default_sequence)

    def test_no_definition_is_silent(self):
        product = self.Product.create(
            {"name": "Plain Door", "is_storable": True, "tracking": "lot"}
        )
        self.assertEqual(product._design_lot_prefix(), "")
        self.assertEqual(product.product_tmpl_id.lot_sequence_id, self.default_sequence)

    def test_conflicting_variants_leave_the_prefix_alone(self):
        """Един шаблон = една последователност ⇒ разминаването не се гадае."""
        attribute = self.env["product.attribute"].create(
            {
                "name": "Test Side",
                "value_ids": [
                    (0, 0, {"name": "Left"}),
                    (0, 0, {"name": "Right"}),
                ],
            }
        )
        template = self.Template.create(
            {
                "name": "Two Sided Door",
                "is_storable": True,
                "tracking": "lot",
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, attribute.value_ids.ids)],
                        },
                    )
                ],
            }
        )
        first, second = template.product_variant_ids[:2]
        first.write(
            {
                "design_param_definition_id": self.definition.id,
                "design_properties": {PREFIX_UUID: "Б"},
            }
        )
        self.assertEqual(template.serial_prefix_format, "Б")
        second.write(
            {
                "design_param_definition_id": self.definition.id,
                "design_properties": {PREFIX_UUID: "И"},
            }
        )
        self.assertEqual(
            template.serial_prefix_format,
            "Б",
            "a variant conflict must not renumber the template",
        )
