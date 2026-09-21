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
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestRender(PocCommon):
    """``{{ код }}`` в текст за цеха (ADR sale-order-poc/0010)."""

    def test_values_replace_the_placeholders(self):
        poc = self._fill(self._make_poc())
        poc._poc_set_params({"t_material": "hdpe", "t_colors": ["red", "blue"]})
        text = poc._poc_render(
            "Width: {{ t_width_mm }}\nMaterial: {{ t_material }}\nColors: {{ t_colors }}"
        )
        # суфиксът на параметъра се показва, селекцията излиза с ЕТИКЕТА си
        self.assertEqual(
            text, "Width: 300 mm\nMaterial: HDPE\nColors: Red, Blue"
        )

    def test_a_line_with_an_empty_value_falls_out(self):
        poc = self._fill(self._make_poc())
        text = poc._poc_render("Width: {{ t_width_mm }}\nPrinter: {{ t_printer }}")
        self.assertEqual(text, "Width: 300 mm")

    def test_extra_values_join_the_configuration(self):
        poc = self._fill(self._make_poc())
        text = poc._poc_render("Make {{ mo_qty }} of {{ t_width_mm }}", extra={"mo_qty": 7})
        self.assertEqual(text, "Make 7 of 300 mm")

    def test_html_escapes_the_values(self):
        poc = self._fill(self._make_poc())
        poc._poc_set_params({"t_printer": self.printer.id})
        self.printer.name = "A & B <Print>"
        text = poc._poc_render("Printer: {{ t_printer }}", fmt="html")
        self.assertIn("&amp;", text)
        self.assertNotIn("<Print>", text)

    def test_checkbox_reads_as_yes_and_false_drops_its_line(self):
        handles = self.env["sale.order.poc.param"].create(
            {"code": "t_handles", "name": "Handles", "param_type": "boolean"}
        )
        self.template.line_ids = [(0, 0, {"sequence": 99, "param_id": handles.id})]
        poc = self._fill(self._make_poc())
        text = "Width: {{ t_width_mm }}\nHandles: {{ t_handles }}"
        poc._poc_set_params({"t_handles": True})
        self.assertEqual(poc._poc_render(text), "Width: 300 mm\nHandles: Yes")
        poc._poc_set_params({"t_handles": False})
        self.assertEqual(poc._poc_render(text), "Width: 300 mm")

    def test_unknown_placeholder_drops_its_line(self):
        poc = self._fill(self._make_poc())
        self.assertEqual(poc._poc_render("Nope: {{ t_nothing }}"), "")
