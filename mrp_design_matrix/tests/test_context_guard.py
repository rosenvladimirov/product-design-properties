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
"""Гардът за липсващ design context.

Дотук `_generate_design_matrix_moves` само записваше warning в лога и
пропускаше матричния пас — MO-то получаваше статичния скелет на рецептата
вместо разгънатия състав, тихо. Мерено на staging 09.09.2026: 54 от 103
матрични MO-та минаваха така (4→18, 3→11 и 39→67 материални реда по една и
съща рецепта). Оттогава нивото е ИЗБОР на вертикала
(`_missing_design_context_level`): базата предупреждава, Солид гърми. Тестът
пази и двете, плюс изхода за миграции.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDesignContextGuard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "Guard test door", "is_storable": True}
        )
        # рецепта с constraint_table ⇒ матричният пас се задейства.
        # Най-малкият граф, който `_check_rule_tables` приема: вход → изход.
        # Празният ({"nodes": []}) се отказва при запис — с него setUpClass
        # падаше и нито един от тестовете тук не се пускаше.
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "product_qty": 1.0,
                "constraint_table": {
                    "nodes": [
                        {"id": "in", "type": "inputNode", "name": "Request"},
                        {"id": "out", "type": "outputNode", "name": "Response"},
                    ],
                    "edges": [{"id": "e1", "sourceId": "in", "targetId": "out"}],
                },
            }
        )
        cls.mo = cls.env["mrp.production"].create(
            {"product_id": cls.product.id, "bom_id": cls.bom.id, "product_qty": 1.0}
        )

    def test_po_podrazbirane_samo_predupregdava(self):
        """Базата пропуска паса с warning — вертикалите без свой конфиг живеят.

        Твърдият гард е ИЗБОР на вертикала (`_missing_design_context_level`).
        Ако базата гърми по подразбиране, MO-тата на вертикал, който законно
        ражда поръчки без конфигурация, спират да се потвърждават.
        """
        self.assertEqual(self.mo._missing_design_context_level(), "warn")
        self.mo._generate_design_matrix_moves()  # без изключение

    def test_bez_kontekst_gyrmi(self):
        """Вертикал с `raise`: MO без нито един източник НЕ минава тихо."""
        self.assertIsNone(
            self.mo._resolve_design_context(), "тестът е валиден само без контекст"
        )
        with patch.object(
            type(self.mo), "_missing_design_context_level", return_value="raise"
        ), self.assertRaises(UserError) as hvanato:
            self.mo._generate_design_matrix_moves()
        self.assertIn(self.mo.name, str(hvanato.exception))
        self.assertIn(
            self.product.display_name,
            str(hvanato.exception),
            "съобщението трябва да казва КОЙ продукт, не само че нещо липсва",
        )

    def test_izhodyat_za_migracii_raboti(self):
        """`skip_design_matrix_guard` пропуска паса, без да гърми."""
        self.mo.with_context(
            skip_design_matrix_guard=True
        )._generate_design_matrix_moves()
        # няма изключение — и нищо не е разгънато
        self.assertFalse(
            self.mo.move_raw_ids.filtered(lambda m: m.created_from_matrix)
            if "created_from_matrix" in self.mo.move_raw_ids._fields
            else False
        )
