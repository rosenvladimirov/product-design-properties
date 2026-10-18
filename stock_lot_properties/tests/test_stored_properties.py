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
"""Записаният речник на Properties се чете както в 18.0.

В 19.0 ``lot.design_params`` е обект ``Property``: изборът идва като етикет,
а 0/"" като ``False``. Сравнението на параметрите на партида (съвпадение на
лот, копиране към дете, ключ при сливане на MO) трябва да вижда записаното.
"""
from odoo.tests import TransactionCase, tagged

SEL = "b1c2d3e4f5a60001"
INT = "b1c2d3e4f5a60002"
CHAR = "b1c2d3e4f5a60003"
FLOAT = "b1c2d3e4f5a60004"
WIDTH = "b1c2d3e4f5a60005"


@tagged("post_install", "-at_install")
class TestStoredProperties(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = cls.env["design.param.definition"].create({
            "code": "test_lot_stored_props",
            "name": "Stored properties (test)",
            "design_params_definition": [
                {
                    "name": SEL,
                    "type": "selection",
                    "string": "Opening",
                    "selection": [["left", "Left hand"], ["right", "Right hand"]],
                },
                {"name": INT, "type": "integer", "string": "Mullions"},
                {"name": CHAR, "type": "char", "string": "Note"},
                {"name": FLOAT, "type": "float", "string": "Offset"},
                {"name": WIDTH, "type": "float", "string": "Width"},
            ],
        })
        cls.product = cls.env["product.product"].create(
            {"name": "Window (test)", "is_storable": True, "tracking": "lot"})
        # Празен char се записва като ``False`` и в 18.0, и в 19.0
        # (``Properties._list_to_dict``) — записаното е ``False``, не "".
        cls.stored = {SEL: "right", INT: 0, CHAR: "RAL 9016", FLOAT: 0.0, WIDTH: 1200.0}
        cls.lot = cls.env["stock.lot"].create({
            "name": "L-STORED",
            "product_id": cls.product.id,
            "design_param_definition_id": cls.definition.id,
            "design_params": dict(cls.stored),
        })

    def test_izborat_e_klyuch_a_nulata_e_nula(self):
        """Ключът на избора и нулата се връщат както са записани.

        През ``Property`` (19.0) изборът е „Right hand“, а 0 и 0.0 — ``False``.
        """
        self.lot.invalidate_recordset()
        raw = self.lot._get_stored_properties()
        self.assertEqual(raw, self.stored)
        self.assertEqual(raw[SEL], "right")
        self.assertIs(type(raw[INT]), int)
        self.assertEqual(raw[INT], 0)
        self.assertIs(type(raw[FLOAT]), float)

    def test_kopie_ne_pipa_kesha(self):
        """Върнатият речник е копие: промяната му не пипа партидата."""
        raw = self.lot._get_stored_properties()
        raw[SEL] = "left"
        self.assertEqual(self.lot._get_stored_properties()[SEL], "right")

    def test_prazno_e_prazen_rechnik(self):
        """Партида без параметри дава ``{}`` (извикващите го ползват с ``or {}``)."""
        lot = self.env["stock.lot"].create(
            {"name": "L-EMPTY", "product_id": self.product.id})
        self.assertEqual(lot._get_stored_properties(), {})

    def test_samo_edna_partida(self):
        """Помощникът е за един запис — две партиди не се сливат тихо."""
        other = self.lot.copy({"name": "L-STORED-2"})
        with self.assertRaises(ValueError):
            (self.lot | other)._get_stored_properties()
