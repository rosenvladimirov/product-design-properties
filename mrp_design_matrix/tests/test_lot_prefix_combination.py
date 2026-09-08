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
"""Lot names resolved from the combination, one sequence per prefix.

Odoo still produces the number — these tests assert which sequence serves
which combination, that a new combination gets its own, and that a prefix
that cannot be resolved never reaches a lot name.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

PREFIX_UUID = "b71c4e0f5a2d4831"
SERIES_UUID = "c2e8a91d4f7b4a60"
POINTS_UUID = "d4b0f27c8e1a4952"


@tagged("post_install", "-at_install")
class TestLotPrefixCombination(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lot = cls.env["stock.lot"]
        cls.Product = cls.env["product.product"]
        cls.Sequence = cls.env["ir.sequence"]
        cls.default_sequence = cls.env.ref(
            "stock.sequence_production_lots", raise_if_not_found=False
        )

        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "test_prefix_combination",
                "name": "Test Prefix Combination",
                "design_params_definition": [
                    {"name": PREFIX_UUID, "type": "char", "string": "Lot Prefix"},
                    {"name": SERIES_UUID, "type": "char", "string": "Series"},
                    {"name": POINTS_UUID, "type": "char", "string": "Lock Points"},
                ],
                "param_dictionary": {
                    "lot_prefix": {"uuid": PREFIX_UUID, "name": {}, "aliases": []},
                    "series": {"uuid": SERIES_UUID, "name": {}, "aliases": []},
                    "lock_points": {"uuid": POINTS_UUID, "name": {}, "aliases": []},
                },
            }
        )

    def _make_product(self, prefix_template, name="Matrix Door"):
        return self.Product.create(
            {
                "name": name,
                "is_storable": True,
                "tracking": "lot",
                "design_param_definition_id": self.definition.id,
                "design_properties": {PREFIX_UUID: prefix_template},
            }
        )

    def _make_lot(self, product, **params):
        design_params = {PREFIX_UUID: product._design_lot_prefix()}
        if "series" in params:
            design_params[SERIES_UUID] = params["series"]
        if "points" in params:
            design_params[POINTS_UUID] = params["points"]
        return self.Lot.create(
            {
                "product_id": product.id,
                "design_param_definition_id": self.definition.id,
                "design_params": design_params,
            }
        )

    # ── the combination decides ──────────────────────────────────────

    def test_template_prefix_is_not_pushed_to_the_product(self):
        """A template cannot serve as the single template-level prefix."""
        product = self._make_product("{series}{lock_points}")
        self.assertTrue(product._design_lot_prefix_is_template())
        self.assertEqual(
            product.product_tmpl_id.lot_sequence_id,
            self.default_sequence,
            "a prefix template must not claim the product sequence",
        )

    def test_lot_name_carries_the_resolved_prefix(self):
        product = self._make_product("{series}{lock_points}")
        lot = self._make_lot(product, series="Е", points="3")
        self.assertTrue(
            lot.name.startswith("Е3"),
            f"lot name {lot.name!r} does not carry the resolved prefix",
        )

    def test_new_combination_gets_its_own_sequence(self):
        product = self._make_product("{series}{lock_points}")
        first = self._make_lot(product, series="Е", points="3")
        second = self._make_lot(product, series="М", points="5")
        self.assertTrue(first.name.startswith("Е3"))
        self.assertTrue(second.name.startswith("М5"))
        self.assertEqual(
            len(self.Sequence.search([("prefix", "in", ["Е3", "М5"])])),
            2,
            "each new combination must get its own sequence",
        )

    def test_same_combination_reuses_its_sequence(self):
        product = self._make_product("{series}{lock_points}")
        first = self._make_lot(product, series="Е", points="3")
        second = self._make_lot(product, series="Е", points="3")
        self.assertEqual(
            len(self.Sequence.search([("prefix", "=", "Е3")])),
            1,
            "the same combination must not create a second sequence",
        )
        self.assertNotEqual(first.name, second.name)

    def test_existing_sequence_for_the_prefix_is_reused(self):
        """Same contract as core: a prefix is served by one sequence only."""
        existing = self.Sequence.create(
            {
                "name": "Pre-existing Г Sequence",
                "code": "stock.lot.serial",
                "prefix": "Г",
                "padding": 7,
                "company_id": False,
            }
        )
        product = self._make_product("{series}")
        self._make_lot(product, series="Г")
        self.assertEqual(
            self.Lot._find_or_create_lot_sequence("Г"),
            existing,
            "a prefix already served by a sequence must not get a second one",
        )

    # ── the cases that must NOT produce a wrong number ───────────────

    def test_unresolvable_template_falls_back(self):
        """Липсващ параметър не бива да роди сгрешен префикс."""
        product = self._make_product("{missing_param}")
        lot = self._make_lot(product, series="Е")
        self.assertFalse(lot.name.startswith("{"))
        self.assertFalse(
            self.Sequence.search([("prefix", "like", "missing")]),
            "an unresolvable template must not create a sequence",
        )

    def test_percent_in_prefix_falls_back(self):
        """ir.sequence интерполира `%(...)s` — префикс с % е капан."""
        product = self._make_product("{series}")
        lot = self._make_lot(product, series="%d")
        self.assertNotIn("%", lot.name)
        self.assertFalse(self.Sequence.search([("prefix", "=", "%d")]))

    def test_ready_prefix_is_left_to_odoo(self):
        """Готовият префикс се носи от полето на продукта, не оттук."""
        product = self._make_product("Б")
        self.assertFalse(product._design_lot_prefix_is_template())
        self.assertEqual(product.product_tmpl_id.serial_prefix_format, "Б")
        lot = self._make_lot(product)
        self.assertTrue(lot.name.startswith("Б"))

    def test_no_prefix_leaves_the_standard_name(self):
        product = self.Product.create(
            {"name": "Plain Matrix Door", "is_storable": True, "tracking": "lot"}
        )
        lot = self.Lot.create({"product_id": product.id})
        self.assertTrue(lot.name)

    def test_combination_wins_over_category_sequence(self):
        """Комбинацията бие категорийната последователност.

        🚨 Приоритетът идва от реда на зареждане: `product_category_lot_sequence`
        зависи само от `stock`, затова пише `name` след нас. Тестът пази точно
        този ред — ако се обърне, номерата ще се сменят тихо.
        """
        if "lot_sequence_id" not in self.env["product.category"]._fields:
            self.skipTest("product_category_lot_sequence is not installed")
        category_sequence = self.Sequence.create(
            {
                "name": "Category К Sequence",
                "code": "stock.lot.serial",
                "prefix": "КАТ",
                "padding": 7,
                "company_id": False,
            }
        )
        category = self.env["product.category"].create(
            {
                "name": "Test Category With Sequence",
                "lot_sequence_id": category_sequence.id,
            }
        )
        product = self._make_product("{series}", name="Both Sources Door")
        product.product_tmpl_id.categ_id = category
        lot = self._make_lot(product, series="Е")
        self.assertTrue(
            lot.name.startswith("Е"),
            f"lot name {lot.name!r} came from the category, not the combination",
        )
