# Copyright 2026 Rosen Vladimirov, Terraros Commerce Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Полуфабрикат на MO, конфигурирано върху самата поръчка, без партида.

Атанас, 20.09.2026: design_params върху MO + потвърждаване →
``_handle_semifinished_lots`` взема ``lot_producing_ids[:1]`` (празно) и
``_create_child_lot`` вика ``ensure_one()`` → Expected singleton.
"""

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSemifinishedWithoutLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "sfl_def",
                "name": "SFL Definition",
                "design_params_definition": [
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "default": "wood",
                        "selection": [
                            ["wood", "Wood"],
                            ["steel", "Steel"],
                            ["glass", "Glass"],
                        ],
                    },
                ],
            }
        )
        cls.door = Product.create(
            {"name": "SFL Door", "is_storable": True, "tracking": "lot"}
        )
        # без поредица: името на детето идва от резервния път
        cls.leaf = Product.create(
            {
                "name": "SFL Leaf",
                "default_code": "SFL-LEAF",
                "is_storable": True,
                "tracking": "lot",
                "lot_sequence_id": False,
            }
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.door.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create(
                        {
                            "product_id": cls.leaf.id,
                            "product_qty": 1.0,
                            "child_definition_id": cls.definition.id,
                        }
                    )
                ],
            }
        )
        cls.line = cls.bom.bom_line_ids

    def _mo(self):
        return self.env["mrp.production"].create(
            {"product_id": self.door.id, "product_qty": 1.0, "bom_id": self.bom.id}
        )

    def _child(self, production):
        move = production.move_raw_ids.filtered(lambda m: m.product_id == self.leaf)
        return move.forced_lot_ids

    def _material(self, lot):
        values = lot.read(["design_params"])[0]["design_params"]
        return {v["name"]: v.get("value") for v in values}["material"]

    def test_mo_without_lot_gets_a_child_lot(self):
        """Без партида-родител параметрите на детето идват от контекста на MO."""
        self.line.param_extraction_map = {"material": "leaf_material"}
        production = self._mo()
        self.assertFalse(production.lot_producing_ids)
        production._handle_semifinished_lots({"leaf_material": "glass"})
        child = self._child(production)
        self.assertEqual(len(child), 1)
        self.assertEqual(child.product_id, self.leaf)
        self.assertEqual(child.design_param_definition_id, self.definition)
        self.assertEqual(self._material(child), "glass")
        # не „False-SFL-LEAF“
        self.assertEqual(child.name, f"{production.name}-SFL-LEAF")
        self.assertFalse(child.company_id)

    def test_lot_path_is_unchanged(self):
        """С партида-родител параметрите се извличат от нея, както досега."""
        parent = self.env["stock.lot"].create(
            {
                "name": "SFL-PARENT",
                "product_id": self.door.id,
                "design_param_definition_id": self.definition.id,
                "design_params": {"material": "steel"},
            }
        )
        # ключът, под който партидата носи материала в контекста си
        key = next(k for k, v in parent._get_design_context().items() if v == "steel")
        self.line.param_extraction_map = {"material": key}
        production = self._mo()
        production.lot_producing_ids = parent
        # контекстът на MO няма този ключ — ако се ползваше, детето щеше да е празно
        production._handle_semifinished_lots({"leaf_material": "glass"})
        child = self._child(production)
        self.assertEqual(self._material(child), "steel")
        self.assertEqual(child.name, "SFL-PARENT-SFL-LEAF")
