# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
"""Съпътстващите редове на офертата (ADR sale-order-poc/0022).

Базата не знае КАКВИ редове — това го казва фирменият слой през
``_poc_companion_lines``. Тук куката се подменя и се проверява само КАК:
създаване, обновяване, ръчна цена, махане, потвърдена оферта, копие.
Всеки тест носи МУТАЦИЯТА, която го уронва.
"""
from unittest.mock import patch

from odoo.tests import tagged

from ..models.sale_order_poc import SaleOrderPoc
from .common import PocCommon


@tagged("post_install", "-at_install")
class TestCompanionLines(PocCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.screen = cls.env["product.product"].create(
            {"name": "TEST screen setup", "type": "service", "list_price": 55.0}
        )
        cls.wanted = []

    def _run(self, poc):
        with patch.object(
            SaleOrderPoc, "_poc_companion_lines", lambda poc: list(self.wanted)
        ):
            poc._poc_compute_derived()

    def _screen(self, price=55.0, qty=1.0):
        return {"key": "screen", "product": self.screen, "qty": qty,
                "price_unit": price}

    def _companion(self, order):
        return order.order_line.filtered("poc_companion_of_id")

    def test_line_is_added_to_the_quotation(self):
        """МУТАЦИЯ: махни `_poc_sync_companion_lines()` от края на
        `_poc_compute_derived` — редът не се появява."""
        poc = self._make_poc()
        self.wanted = [self._screen()]
        self._run(poc)
        line = self._companion(poc.order_id)
        self.assertEqual(line.product_id, self.screen)
        self.assertEqual(line.price_unit, 55.0)
        self.assertEqual(line.poc_companion_of_id, poc)

    def test_recompute_does_not_duplicate_and_updates(self):
        """МУТАЦИЯ: търси съществуващия ред не по `poc_companion_key` —
        второто преизчисляване добавя втори ред."""
        poc = self._make_poc()
        self.wanted = [self._screen()]
        self._run(poc)
        self.wanted = [self._screen(price=0.0, qty=2.0)]
        self._run(poc)
        line = self._companion(poc.order_id)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.price_unit, 0.0)
        self.assertEqual(line.product_uom_qty, 2.0)

    def test_price_changed_by_hand_is_kept(self):
        """МУТАЦИЯ: пиши цената винаги, без проверката за ръчна цена."""
        poc = self._make_poc()
        self.wanted = [self._screen()]
        self._run(poc)
        line = self._companion(poc.order_id)
        line.price_unit = 40.0
        self.wanted = [self._screen(price=0.0)]
        self._run(poc)
        self.assertEqual(line.price_unit, 40.0)

    def test_line_no_longer_wanted_is_removed(self):
        """МУТАЦИЯ: махни `unlink` на ненужните ключове."""
        poc = self._make_poc()
        self.wanted = [self._screen()]
        self._run(poc)
        self.wanted = []
        self._run(poc)
        self.assertFalse(self._companion(poc.order_id))

    def test_confirmed_order_is_not_touched(self):
        """МУТАЦИЯ: махни проверката за `draft`/`sent`."""
        order = self._make_order()
        poc = self._make_poc(order)
        self._fill(poc)
        order.action_confirm()
        self.wanted = [self._screen()]
        self._run(poc)
        self.assertFalse(self._companion(order))

    def test_deleting_the_configuration_removes_its_lines(self):
        """МУТАЦИЯ: `ondelete="set null"` на `poc_companion_of_id`."""
        poc = self._make_poc()
        order = poc.order_id
        self.wanted = [self._screen()]
        self._run(poc)
        poc.unlink()
        self.assertFalse(order.order_line.filtered(
            lambda line: line.product_id == self.screen))

    def test_copy_does_not_duplicate(self):
        """МУТАЦИЯ: махни `_get_copiable_order_lines` от sale.order."""
        poc = self._make_poc()
        self.wanted = [self._screen()]
        self._run(poc)
        with patch.object(
            SaleOrderPoc, "_poc_companion_lines", lambda poc: list(self.wanted)
        ):
            copy = poc.order_id.copy()
        lines = copy.order_line.filtered(
            lambda line: line.product_id == self.screen)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.poc_companion_of_id, copy.poc_ids)

    def test_repeat_order_is_known_by_the_lot(self):
        """Втора оферта със същия лот знае, че лотът вече е поръчан.

        МУТАЦИЯ: `_poc_design_lot_ordered` връща винаги False.
        """
        first = self._make_order()
        poc1 = self._make_poc(first)
        self._fill(poc1)
        first.action_confirm()
        self.assertTrue(poc1.lot_id)
        poc2 = self._make_poc()
        self.assertFalse(poc2._poc_design_lot_ordered())
        poc2.with_context(poc_system=True).sudo().lot_id = poc1.lot_id
        self.assertTrue(poc2._poc_design_lot_ordered())
