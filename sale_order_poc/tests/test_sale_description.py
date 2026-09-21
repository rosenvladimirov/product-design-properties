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

TEXT = "Width: {{ t_width_mm }}\nPrinter: {{ t_printer }}"


@tagged("post_install", "-at_install")
class TestSaleDescription(PocCommon):
    """Текстът на конфигурацията в офертата (ADR sale-order-poc/0017).

    Клиентът одобрява конфигурацията с офертата, затова тя трябва да е в
    описанието на реда — и да следва промените, докато офертата не е приета.
    """

    def _line_with_poc(self):
        self.template.sale_description = TEXT
        order = self._make_order()
        product_text = order.order_line.name
        poc = self._fill(self._make_poc(order))
        return order, order.order_line, product_text, poc

    def test_block_joins_the_product_text(self):
        _order, line, product_text, _poc = self._line_with_poc()
        # принтерът е празен ⇒ редът му изпада
        self.assertEqual(line.name, f"{product_text}\n\nWidth: 300 mm")

    def test_change_replaces_the_block(self):
        _order, line, product_text, poc = self._line_with_poc()
        self._fill(poc, width=450.0)
        self.assertEqual(line.name, f"{product_text}\n\nWidth: 450 mm")

    def test_text_around_the_block_stays(self):
        _order, line, _product_text, poc = self._line_with_poc()
        line.name = f"Intro\n{line.name}\nThanks"
        self._fill(poc, width=450.0)
        self.assertTrue(line.name.startswith("Intro\n"))
        self.assertTrue(line.name.endswith("Width: 450 mm\nThanks"))
        self.assertEqual(line.name.count("Width:"), 1)

    def test_hand_edited_block_is_not_overwritten(self):
        _order, line, _product_text, poc = self._line_with_poc()
        line.name = line.name.replace("300 mm", "310 mm (agreed by phone)")
        messages = len(poc.message_ids)
        self._fill(poc, width=450.0)
        self.assertIn("310 mm (agreed by phone)", line.name)
        self.assertNotIn("450 mm", line.name)
        self.assertGreater(
            len(poc.message_ids), messages, "the chatter must say the text was left"
        )

    def test_accepted_quotation_keeps_its_text(self):
        order, line, product_text, poc = self._line_with_poc()
        order.action_confirm()
        poc.with_user(self.manager).write(
            {"params": {**poc.params._values, "t_width_mm": 310.0}}
        )
        self.assertEqual(line.name, f"{product_text}\n\nWidth: 300 mm")

    def test_salesman_without_the_order_still_saves(self):
        """Продавач, който не чете поръчката, пак записва POC (tour-ът го хвана)."""
        _order, line, product_text, poc = self._line_with_poc()
        poc.with_user(self.pure_salesman).write(
            {"params": {**poc.params._values, "t_width_mm": 450.0}}
        )
        self.assertEqual(line.name, f"{product_text}\n\nWidth: 450 mm")

    def test_template_without_text_leaves_the_line(self):
        order = self._make_order()
        product_text = order.order_line.name
        self._fill(self._make_poc(order))
        self.assertEqual(order.order_line.name, product_text)
