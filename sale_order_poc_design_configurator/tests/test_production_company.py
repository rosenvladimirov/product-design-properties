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
"""POC на продаващата фирма стига до MO на фирмата производител.

Солид: СДЦ продава с POC, Продакшън произвежда по огледалната продажба, в
която POC няма. Връзката е дизайн партидата — осиновена от POC, тя носи
``poc_id``. Потребителят в Продакшън не вижда POC на СДЦ (фирменото
правило), но работи с MO, който е вързан за него.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.sale_order_poc_design_matrix.tests.common import MatrixPocCommon


@tagged("post_install", "-at_install")
class TestProductionCompany(MatrixPocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env["res.company"].create({"name": "POC Production"})
        cls.warehouse_b = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company_b.id)], limit=1
        )
        cls.bom.copy({"company_id": cls.company_b.id})
        cls.product.route_ids = [(4, cls.warehouse_b.manufacture_pull_id.route_id.id)]
        cls.user_b = new_test_user(
            cls.env,
            login="poc_production_b",
            groups="mrp.group_mrp_user,stock.group_stock_user",
            company_id=cls.company_b.id,
            company_ids=[cls.company_b.id],
        )

    def _adopted(self):
        """POC на СДЦ осиновява партидата без фирма, както от кубчето."""
        order = self._make_order(qty=2.0)
        poc = self._fill(self._make_poc(order))
        lot = self.env["stock.lot"].create(
            {"product_id": self.product.id, "name": "DESIGN-B-0001"}
        )
        order.order_line[:1].design_lot_id = lot.id
        poc._poc_ensure_lot()
        self.assertEqual(lot.poc_id, poc)
        return poc, lot

    def _procure_in_b(self, lot, qty=2.0):
        """Огледалната продажба в Продакшън: процюърмънт само с партидата."""
        Rule = self.env["stock.rule"]
        Rule.with_company(self.company_b).run(
            [
                Rule.Procurement(
                    self.product,
                    qty,
                    self.product.uom_id,
                    self.warehouse_b.lot_stock_id,
                    "MIRROR",
                    "MIRROR",
                    self.company_b,
                    {"warehouse_id": self.warehouse_b, "design_lot_id": lot.id},
                )
            ]
        )
        return self.env["mrp.production"].search(
            [
                ("company_id", "=", self.company_b.id),
                ("product_id", "=", self.product.id),
            ]
        )

    def test_mo_of_the_production_company_carries_the_poc(self):
        poc, lot = self._adopted()
        production = self._procure_in_b(lot)
        self.assertEqual(len(production), 1)
        self.assertEqual(production.poc_id, poc)
        self.assertEqual(production.lot_producing_ids, lot)
        self.assertIn(poc.summary, production.product_description_variants)

    def test_production_user_opens_and_finishes_the_mo(self):
        """Без достъп до POC на СДЦ: формата се отваря, MO се довършва."""
        poc, lot = self._adopted()
        # предпоставката: POC на СДЦ е скрит за Продакшън
        with self.assertRaises(AccessError):
            poc.with_user(self.user_b).check_access("read")
        production = self._procure_in_b(lot)
        # без връзката MO не чете нищо от POC и тестът не доказва нищо
        self.assertEqual(production.poc_id, poc)
        production = production.with_user(self.user_b)
        production.web_read(
            {
                "poc_id": {"fields": {"display_name": {}}},
                "poc_summary": {},
                "poc_params": {},
                "poc_mo_params": {},
            }
        )
        production.action_confirm()
        form = Form(production)
        form.qty_producing = 2.0
        production = form.save()
        production.button_mark_done()
        self.assertEqual(production.state, "done")

    def test_poc_change_reaches_the_production_company(self):
        """Промяна на POC в СДЦ стига до незапочнатото MO в Продакшън."""
        poc, lot = self._adopted()
        production = self._procure_in_b(lot)
        production.action_confirm()
        Production = self.registry["mrp.production"]
        original = Production._poc_refresh
        seen = []

        def spy(records):
            seen.extend(records.ids)
            return original(records)

        with patch.object(Production, "_poc_refresh", spy):
            poc._poc_set_params({"t_width_mm": 400.0})
            poc._poc_compute_derived()
        self.assertIn(production.id, seen)
