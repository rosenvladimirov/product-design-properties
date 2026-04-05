# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
Tests for ``design.param.definition``:

- ``full_design_params_definition`` merges the parent chain correctly
- Child definitions override parent properties with the same name
- Unique code constraint is enforced
- Empty definitions return empty merged list
"""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestDefinition(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Definition = cls.env["design.param.definition"]

    # ── Full definition computation ──────────────────────────────────

    def test_own_properties_only(self):
        """A definition with no parent returns its own properties."""
        defn = self.Definition.create(
            {
                "code": "test_own",
                "name": "Own Only",
                "design_params_definition": [
                    {
                        "name": "width",
                        "type": "float",
                        "string": "Width",
                        "default": "900",
                    },
                ],
            }
        )
        full = defn.full_design_params_definition
        self.assertEqual(len(full), 1)
        self.assertEqual(full[0]["name"], "width")

    def test_parent_chain_merge(self):
        """Parent properties are inherited into the child's full definition."""
        parent = self.Definition.create(
            {
                "code": "test_parent",
                "name": "Base",
                "design_params_definition": [
                    {
                        "name": "width",
                        "type": "float",
                        "string": "Width",
                        "default": "900",
                    },
                    {
                        "name": "height",
                        "type": "float",
                        "string": "Height",
                        "default": "2100",
                    },
                ],
            }
        )
        child = self.Definition.create(
            {
                "code": "test_child",
                "name": "Child",
                "parent_id": parent.id,
                "design_params_definition": [
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
        full = child.full_design_params_definition
        strings = {p.get("string") for p in full}
        # Child should see its own + parent's properties
        self.assertIn("Material", strings)
        self.assertIn("Width", strings)
        self.assertIn("Height", strings)
        self.assertEqual(len(full), 3)

    def test_child_overrides_parent_property(self):
        """A child property with the same ``string`` replaces the parent's."""
        parent = self.Definition.create(
            {
                "code": "test_parent_override",
                "name": "Base",
                "design_params_definition": [
                    {
                        "name": "width",
                        "type": "float",
                        "string": "Width",
                        "default": "900",
                    },
                ],
            }
        )
        child = self.Definition.create(
            {
                "code": "test_child_override",
                "name": "Child",
                "parent_id": parent.id,
                "design_params_definition": [
                    {
                        "name": "width",
                        "type": "float",
                        "string": "Width",
                        "default": "1200",
                    },
                ],
            }
        )
        full = child.full_design_params_definition
        widths = [p for p in full if p.get("string") == "Width"]
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths[0]["default"], "1200")

    def test_empty_definition_has_empty_full(self):
        """A definition with no properties and no parent has an empty full."""
        defn = self.Definition.create(
            {"code": "test_empty", "name": "Empty"}
        )
        self.assertEqual(defn.full_design_params_definition or [], [])

    # ── Constraints ──────────────────────────────────────────────────

    def test_unique_code_constraint(self):
        """Creating two definitions with the same code raises."""
        self.Definition.create({"code": "dup_code", "name": "First"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Definition.create({"code": "dup_code", "name": "Second"})

    # ── Grandchild chain ─────────────────────────────────────────────

    def test_three_level_chain(self):
        """Parent → Child → Grandchild all merge together."""
        base = self.Definition.create(
            {
                "code": "chain_base",
                "name": "Base",
                "design_params_definition": [
                    {"name": "width", "type": "float", "string": "Width"},
                ],
            }
        )
        middle = self.Definition.create(
            {
                "code": "chain_middle",
                "name": "Middle",
                "parent_id": base.id,
                "design_params_definition": [
                    {"name": "height", "type": "float", "string": "Height"},
                ],
            }
        )
        leaf = self.Definition.create(
            {
                "code": "chain_leaf",
                "name": "Leaf",
                "parent_id": middle.id,
                "design_params_definition": [
                    {"name": "thickness", "type": "float", "string": "Thickness"},
                ],
            }
        )
        strings = {p.get("string") for p in leaf.full_design_params_definition}
        self.assertEqual(strings, {"Width", "Height", "Thickness"})
