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
from odoo.tests import HttpCase, tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestPocUi(PocCommon, HttpCase):
    """Формата на POC в браузъра — пълна база не значи работещ екран."""

    def _url(self, poc):
        return "/odoo/action-sale_order_poc.sale_order_poc_action/%d" % poc.id

    def test_salesman_fills_and_saves(self):
        poc = self._make_poc()
        self.start_tour(
            self._url(poc), "sale_order_poc_salesman", login="poc_pure_salesman"
        )
        values = poc._poc_values()
        self.assertEqual(values["t_width_mm"], 300.0)
        self.assertAlmostEqual(values["t_weight_g"], 5.52)

    def test_manager_reaches_the_definition_editor(self):
        poc = self._make_poc()
        self.start_tour(self._url(poc), "sale_order_poc_manager", login="poc_manager")

    def test_aspect_parameters_are_edited_in_the_popup(self):
        """Аспектът се редактира в изскачащия прозорец (ADR sale-order-poc/0004)."""
        param = self.env["sale.order.poc.param"].create(
            {"code": "t_print_colors", "name": "Print Colors", "param_type": "integer"}
        )
        aspect_template = self.env["sale.order.poc.template"].create(
            {
                "code": "t_print",
                "name": "Printing",
                "usage": "aspect",
                "line_ids": [(0, 0, {"param_id": param.id})],
            }
        )
        self.template.allowed_aspect_ids = [(4, aspect_template.id)]
        poc = self._fill(self._make_poc())
        self.env["sale.order.poc.aspect"].create(
            {"poc_id": poc.id, "template_id": aspect_template.id}
        )
        self.start_tour(self._url(poc), "sale_order_poc_aspect", login="poc_pure_salesman")
        self.assertEqual(poc._poc_values()["t_print_colors"], 6)
