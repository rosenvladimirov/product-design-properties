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
"""Името на нов лот от конфигуратора (``generate_design_lot_name``).

Заковава 19.0.1.50.0: при сливането с дървото на Packit функцията се върна
към ``next_by_code("stock.lot.serial")`` и никой тест не падна, защото такъв
нямаше. Двата пътя, които тя трябва да спазва:

- комбинацията решава, когато продуктът носи шаблон за префикс;
- без шаблон — поредицата на продукта, а не първата с кода
  ``stock.lot.serial`` (ядрото ражда по една с този код за всеки префикс).
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

PREFIX_UUID = "5e0a3c7d9b1f4e28"
SERIES_UUID = "6f1b4d8e0c2a4f39"
POINTS_UUID = "7a2c5e9f1d3b4a40"


@tagged("post_install", "-at_install")
class TestDesignLotName(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lot = cls.env["stock.lot"]
        cls.Product = cls.env["product.product"]
        cls.Sequence = cls.env["ir.sequence"]

        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "test_configurator_lot_name",
                "name": "Test Configurator Lot Name",
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

    def test_combination_decides_the_name(self):
        """Конфигураторът подава комбинацията и тя дава префикса."""
        product = self.Product.create(
            {
                "name": "Configurator Door",
                "is_storable": True,
                "tracking": "lot",
                "design_param_definition_id": self.definition.id,
                "design_properties": {PREFIX_UUID: "{series}{lock_points}"},
            }
        )
        params = {
            PREFIX_UUID: product._design_lot_prefix(),
            SERIES_UUID: "Е",
            POINTS_UUID: "3",
        }
        name = self.Lot.generate_design_lot_name(
            product.id, params, self.definition.id
        )
        self.assertTrue(
            name.startswith("Е3"),
            f"lot name {name!r} does not carry the prefix of the combination",
        )

    def test_product_sequence_not_first_by_code(self):
        """Без шаблон отговаря поредицата на продукта, не първата по код."""
        # Чужд префикс: ядрото създава поредица със същия код за всеки
        # префикс. Фирмата ѝ я слага първа в търсенето по код.
        self.Sequence.create(
            {
                "name": "Other Product Lot Sequence",
                "code": "stock.lot.serial",
                "prefix": "OTHER/",
                "padding": 5,
                "company_id": self.env.company.id,
            }
        )
        own = self.Sequence.create(
            {
                "name": "Own Product Lot Sequence",
                "code": "stock.lot.serial",
                "prefix": "OWN/",
                "padding": 5,
                "company_id": False,
            }
        )
        product = self.Product.create(
            {"name": "Plain Product", "is_storable": True, "tracking": "lot"}
        )
        product.product_tmpl_id.lot_sequence_id = own
        name = self.Lot.generate_design_lot_name(product.id)
        self.assertTrue(
            name.startswith("OWN/"),
            f"lot name {name!r} is not from the product's own sequence",
        )
