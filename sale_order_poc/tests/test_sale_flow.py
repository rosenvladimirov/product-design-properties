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
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestSaleFlow(PocCommon):
    def test_confirm_without_configuration_is_refused(self):
        order = self._make_order()
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_confirm_with_missing_required_is_refused(self):
        order = self._make_order()
        self._make_poc(order)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_salesman_configures_and_confirms(self):
        self._check_salesman_flow(self.salesman)

    def test_pure_salesman_configures_and_confirms(self):
        """Същото без складови права: лотът и процюърмънтът не искат склад."""
        self._check_salesman_flow(self.pure_salesman)

    def _check_salesman_flow(self, user):
        """Продавач без права на мениджър ражда, попълва и потвърждава.

        Лотът се ражда преди процюърмънта и движението на доставката носи
        конфигурацията и ограничението по лотовете ѝ.
        """
        env = self.env(user=user)
        order = env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 100.0})
                ],
            }
        )
        action = order.order_line.action_open_poc()
        poc = env["sale.order.poc"].browse(action["res_id"])
        self._fill(poc)
        order.action_confirm()
        self.assertEqual(poc.state, "confirmed")
        lot = poc.lot_id
        self.assertTrue(lot)
        self.assertEqual(lot.poc_id, poc)
        self.assertEqual(lot.poc_batch, 1)
        self.assertEqual(lot.product_id, self.product)
        move = order.order_line.move_ids
        self.assertEqual(move.poc_id, poc)
        self.assertTrue(move.poc_lot_restrict)

    def test_lot_name_without_product_sequence(self):
        """Продукт без поредност взима стандартната поредност на Odoo."""
        standard = self.env.ref("stock.sequence_production_lots")
        expected = standard.get_next_char(standard.number_next_actual)
        self.product.product_tmpl_id.lot_sequence_id = False
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        self.assertEqual(poc.lot_id.name, expected)
        self.assertNotIn(poc.name, poc.lot_id.name)

    def test_lot_name_from_product_prefix(self):
        """Префиксът на продукта дава името на лота."""
        self.product.product_tmpl_id.serial_prefix_format = "POCTEST-"
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        self.assertTrue(poc.lot_id.name.startswith("POCTEST-"))

    def test_quantity_change_on_confirmed_line_recomputes(self):
        """Промяна на количеството пуска Stage 1 преди процюърмънта."""
        total = self.env["sale.order.poc.param"].create(
            {"code": "t_bags_total", "name": "Bags", "param_type": "float"}
        )
        self.template.write(
            {
                "line_ids": [
                    (0, 0, {"sequence": 60, "param_id": total.id, "formula": "result = order_qty"})
                ]
            }
        )
        order = self._make_order(qty=100.0)
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        self.assertEqual(poc._poc_values()["t_bags_total"], 100.0)
        order.order_line.product_uom_qty = 250.0
        self.assertEqual(poc._poc_values()["t_bags_total"], 250.0)

    def test_line_added_to_confirmed_order_waits_for_release(self):
        order = self._make_order(qty=10.0)
        self._fill(self._make_poc(order))
        order.action_confirm()
        order.write(
            {"order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 5.0})]}
        )
        new_line = order.order_line.filtered(lambda line: not line.poc_id)
        self.assertEqual(len(new_line), 1)
        self.assertFalse(new_line.move_ids)
        poc = self._fill(
            self.env["sale.order.poc"].create({"sale_line_id": new_line.id})
        )
        self.assertTrue(poc.release_needed)
        poc.action_release()
        self.assertTrue(new_line.move_ids)
        self.assertEqual(new_line.move_ids.poc_id, poc)
        self.assertFalse(poc.release_needed)

    def test_copy_order_copies_configuration_without_lot(self):
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        new_order = order.copy()
        new_poc = new_order.order_line.poc_id
        self.assertTrue(new_poc)
        self.assertNotEqual(new_poc, poc)
        self.assertFalse(new_poc.lot_id)
        self.assertEqual(new_poc.state, "draft")
        self.assertEqual(new_poc._poc_values()["t_width_mm"], 300.0)
        self.assertEqual(new_poc.summary, poc.summary)

    def test_cancel_order_cancels_configuration(self):
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order._action_cancel()
        self.assertEqual(poc.state, "cancel")


@tagged("post_install", "-at_install")
class TestSecurity(PocCommon):
    def test_salesman_cannot_edit_template(self):
        with self.assertRaises(AccessError):
            self.template.with_user(self.salesman).name = "Hacked"

    def test_confirmed_configuration_is_locked_for_salesman(self):
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        as_salesman = poc.with_user(self.salesman)
        with self.assertRaises(UserError):
            as_salesman.write({"params": {**poc.params._values, "t_width_mm": 1.0}})
        as_manager = poc.with_user(self.manager)
        messages = len(poc.message_ids)
        as_manager.write({"params": {**poc.params._values, "t_width_mm": 310.0}})
        self.assertEqual(poc._poc_values()["t_width_mm"], 310.0)
        # разликата отива в чатъра
        self.assertGreater(len(poc.message_ids), messages)

    def test_template_cannot_change_after_confirmation(self):
        order = self._make_order()
        poc = self._fill(self._make_poc(order))
        order.action_confirm()
        other = self.template.copy({"code": "t_bag_copy"})
        with self.assertRaises(UserError):
            poc.with_user(self.manager).template_id = other
