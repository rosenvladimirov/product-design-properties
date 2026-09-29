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
"""Една поръчка — една партида (ADR sale-order-poc/0019).

Стъпва на основата на POC модула: речник, шаблон, продукт с партиди и
поръчка. Отгоре идва партидата на дизайна, както я ражда конфигураторът.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.sale_order_poc_design_matrix.tests.common import (
    BOARD,
    MatrixPocCommon,
    U,
)


@tagged("post_install", "-at_install")
class TestLotAdoption(MatrixPocCommon):
    def _poc_on_order(self, qty=100.0):
        order = self._make_order(qty=qty)
        return order, self._fill(self._make_poc(order))

    def _design_lot(self, product=None, name="DESIGN-0001", **vals):
        return self.env["stock.lot"].create(
            {
                "product_id": (product or self.product).id,
                "name": name,
                "company_id": self.env.company.id,
                **vals,
            }
        )

    def test_poc_adopts_the_design_lot(self):
        """Партидата е една и носи и двете: дизайна и конфигурацията."""
        order, poc = self._poc_on_order()
        lot = self._design_lot()
        order.order_line[:1].design_lot_id = lot.id

        poc._poc_ensure_lot()

        self.assertEqual(poc.lot_id, lot, "POC трябва да осинови партидата на реда")
        self.assertEqual(lot.poc_id, poc)
        self.assertEqual(lot.poc_batch, 1)
        self.assertEqual(
            self.env["stock.lot"].search_count([("product_id", "=", self.product.id)]),
            1,
            "втора партида значи две истини за една поръчка",
        )

    def test_without_a_design_lot_the_poc_makes_its_own(self):
        """Ред без конфигуратор минава по стандартния път на POC."""
        _order, poc = self._poc_on_order()
        poc._poc_ensure_lot()
        self.assertTrue(poc.lot_id)
        self.assertEqual(poc.lot_id.poc_id, poc)

    def test_a_lot_of_another_configuration_is_refused(self):
        """Чужда партида не се преподписва тихо — семейството ѝ е чуждо."""
        order_a, poc_a = self._poc_on_order()
        lot = self._design_lot()
        order_a.order_line[:1].design_lot_id = lot.id
        poc_a._poc_ensure_lot()

        order_b, poc_b = self._poc_on_order()
        order_b.order_line[:1].design_lot_id = lot.id
        with self.assertRaises(UserError):
            poc_b._poc_ensure_lot()

    def test_a_lot_of_another_product_is_left_alone(self):
        """Партида на друг продукт не описва това изделие — не се осиновява."""
        order, poc = self._poc_on_order()
        other = self.env["product.product"].create(
            {"name": "Other Product (test)", "is_storable": True, "tracking": "lot"}
        )
        lot = self._design_lot(product=other, name="DESIGN-OTHER")
        order.order_line[:1].design_lot_id = lot.id

        poc._poc_ensure_lot()

        self.assertFalse(lot.poc_id, "чуждата партида остава непокътната")
        self.assertTrue(poc.lot_id)
        self.assertNotEqual(poc.lot_id, lot)
        self.assertEqual(poc.lot_id.product_id, self.product)

    def test_adoption_is_idempotent(self):
        """Второ потвърждаване не ражда втора партида и не сменя номера."""
        order, poc = self._poc_on_order()
        lot = self._design_lot()
        order.order_line[:1].design_lot_id = lot.id
        poc._poc_ensure_lot()
        poc._poc_ensure_lot()
        self.assertEqual(poc.lot_id, lot)
        self.assertEqual(lot.poc_batch, 1)
        self.assertEqual(
            self.env["stock.lot"].search_count([("poc_id", "=", poc.id)]), 1
        )

    def test_the_confirmed_lot_is_the_fixed_design_lot(self):
        """Кубчето на поръчката отваря партидата на POC, не ражда втора."""
        order, poc = self._poc_for_matrix()
        order.action_confirm()
        line = order.order_line
        self.assertTrue(poc.lot_id)
        self.assertEqual(line.design_lot_id, poc.lot_id)
        self.assertEqual(poc.lot_id.design_state, "sales_confirmed")

    def test_a_pure_salesman_confirms(self):
        """Партидата се фиксира системно: продавачът няма складови права."""
        order, poc = self._poc_for_matrix()
        # своя поръчка: продавачът вижда и пише само своите
        order.user_id = self.pure_salesman
        order.with_user(self.pure_salesman).action_confirm()
        self.assertEqual(order.order_line.design_lot_id, poc.lot_id)
        self.assertEqual(poc.lot_id.design_state, "sales_confirmed")

    def test_the_adopted_lot_keeps_the_configurator_values(self):
        """Партидата на конфигуратора пази своите; POC пише само своите."""
        order, poc = self._poc_for_matrix()
        lot = self._design_lot(
            name="DESIGN-MATRIX-1",
            design_param_definition_id=self.definition.id,
            design_params={U["t_trim_waste"]: 0.07, U["t_width_mm"]: 450.0},
        )
        order.order_line.design_lot_id = lot
        order.action_confirm()
        self.assertEqual(poc.lot_id, lot)
        values = lot.design_params._values
        self.assertEqual(values[U["t_trim_waste"]], 0.07)  # на конфигуратора
        self.assertEqual(values[U["t_width_mm"]], 300.0)  # POC управлява размера
        self.assertEqual(values[U["t_board"]], BOARD)
