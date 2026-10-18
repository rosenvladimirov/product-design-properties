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
"""Съвпадението на лот и контекстът четат записаното, както в 18.0.

В 19.0 ``lot.design_params`` е ``Property``: изборът идва като етикет, а
0 като ``False``. Без суровото четене ``_find_matching_stock_lot`` не
намира съществуващ лот (``mto_stop``) и се ражда нов, а контекстът на
формулите получава ``False`` вместо 0.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStoredParamsMatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {
                "name": "Stored params product (test)",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "test_stored_match",
                "name": "Stored params match (test)",
                "design_params_definition": [
                    {"name": "mullions", "type": "integer", "string": "Mullions"},
                    {
                        "name": "material",
                        "type": "selection",
                        "string": "Material",
                        "selection": [["wood", "Wood"], ["steel", "Steel"]],
                    },
                ],
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "name": "TEST-STORED-MATCH",
                "product_id": cls.product.id,
                "design_param_definition_id": cls.definition.id,
                "design_params": {"mullions": 0, "material": "steel"},
            }
        )

    def test_savpada_po_klyuch_i_nula(self):
        """Ключът на избора и нулата намират записания лот."""
        self.lot.invalidate_recordset()
        found = self.env["stock.lot"]._find_matching_stock_lot(
            self.product, {"mullions": 0, "material": "steel"}
        )
        self.assertEqual(found, self.lot)

    def test_etiketat_ne_savpada(self):
        """Етикетът на избора не е записаната стойност — не съвпада."""
        found = self.env["stock.lot"]._find_matching_stock_lot(
            self.product, {"material": "Steel"}
        )
        self.assertFalse(found)

    def test_kontekstat_nosi_nulata(self):
        """Контекстът на формулите получава 0 (int), не ``False``."""
        self.lot.invalidate_recordset()
        ctx = self.lot._get_design_context()
        self.assertIs(type(ctx["Mullions"]), int)
        self.assertEqual(ctx["Mullions"], 0)
        self.assertEqual(ctx["Material"], "steel")
