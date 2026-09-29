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
"""Иконите на реда и кубчето — в браузъра (ADR sale-order-poc/0019).

На 21.09 куката за кубчето беше вързана за Python действие, а кубчето на реда
отваря диалога директно: сървърът и пакетът бяха „зелени“, екранът — не.
"""

from odoo.tests import HttpCase, tagged

from odoo.addons.sale_order_poc_design_matrix.tests.common import MatrixPocCommon


@tagged("post_install", "-at_install")
class TestPocDesignIcons(HttpCase, MatrixPocCommon):
    def test_icons_follow_the_order_and_the_cube_shows_the_lot(self):
        order, _poc = self._poc_for_matrix(qty=10.0)
        self.start_tour(
            f"/odoo/action-sale.action_orders/{order.id}",
            "sale_order_poc_design_icons",
            login="admin",
        )
        self.assertEqual(order.state, "sale")
