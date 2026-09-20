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
from odoo.tests import HttpCase, new_test_user, tagged

from .common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestPocMrpUi(PocMrpCommon, HttpCase):
    """Формата на MO в браузъра, с правата на плановика."""

    def test_planner_sees_and_recomputes(self):
        new_test_user(self.env, login="poc_planner", groups="mrp.group_mrp_user")
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        self.start_tour(
            "/odoo/action-mrp.mrp_production_action/%d" % production.id,
            "sale_order_poc_mrp_planner",
            login="poc_planner",
        )
