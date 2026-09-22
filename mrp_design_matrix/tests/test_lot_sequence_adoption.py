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
"""Една буква — една поредица.

Фамилните поредици пазят ШАБЛОН за интерполация („Б%(range_y)s"), а
комбинацията разрешава префикса до буквален низ („Б26") още преди търсенето.
Търсене по буквален низ никога не ги намира ⇒ ражда се втора поредица за
същото семейство и същата година, с друг padding.

Мерено на staging 10.09.2026: 139 „Lot/Serial — Блиндирани врати (Б)"
(padding 4, диапазон 2026, следващ 28) и 136 „Блиндирана врата Serial
Sequence" (padding 7) — Б260028 срещу Б260000001. Едно семейство, две
пространства на номера, и по още една поредица на всяка нова година.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestLotSequenceAdoption(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Sequence = cls.env["ir.sequence"]
        cls.Lot = cls.env["stock.lot"]

    def test_priema_familnata_vmesto_da_sazdava_vtora(self):
        """Интерполиран префикс, който съвпада, се ПРИЕМА, не се дублира."""
        familna = self.Sequence.create({
            "name": "ТЕСТ — Фамилна (Я)",
            "prefix": "Я%(range_y)s",
            "padding": 4,
            "use_date_range": True,
            "company_id": False,
        })
        razreshen, _suffix = familna._get_prefix_suffix()
        broy_predi = self.Sequence.search_count([("prefix", "like", "Я")])

        namerena = self.Lot._find_or_create_lot_sequence(razreshen)

        self.assertEqual(
            namerena, familna,
            "разрешеният префикс се сервира от фамилната поредица — тя се приема",
        )
        self.assertEqual(
            self.Sequence.search_count([("prefix", "like", "Я")]), broy_predi,
            "не бива да се ражда втора поредица за същото семейство",
        )

    def test_neznaen_prefiks_vse_pak_razhda_poredica(self):
        """Гардът не бива да спира истински новите префикси."""
        broy_predi = self.Sequence.search_count([("prefix", "like", "Ю")])
        nova = self.Lot._find_or_create_lot_sequence("Ю2699")
        self.assertTrue(nova, "нов префикс без стопанин ражда своя поредица")
        self.assertEqual(nova.prefix, "Ю2699")
        self.assertEqual(
            self.Sequence.search_count([("prefix", "like", "Ю")]), broy_predi + 1)

    def test_tochnoto_savpadenie_ostava_nay_burzo(self):
        """Буквално еднакъв префикс се намира без интерполация."""
        tochna = self.Sequence.create({
            "name": "ТЕСТ — Буквална (Э)",
            "prefix": "Э26",
            "padding": 7,
            "company_id": False,
        })
        self.assertEqual(self.Lot._find_or_create_lot_sequence("Э26"), tochna)
