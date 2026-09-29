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
"""Кубчето на реда показва POC, докато партидата не е фиксирана.

ADR sale-order-poc/0019.
"""

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.sale_design_configurator.models import (
    design_param_definition as base_definition,
)
from odoo.addons.sale_order_poc_design_matrix.tests.common import (
    BOARD,
    MatrixPocCommon,
    U,
)


@tagged("post_install", "-at_install")
class TestParamOverlay(MatrixPocCommon):
    def _patch(self, line, screen, changed_key=False):
        return (
            self.env["design.param.definition"]
            .with_context(design_sale_line_id=line.id if line else False)
            .get_param_patch(self.definition.id, changed_key, screen)
        )

    def test_the_configurator_opens_with_the_poc_values(self):
        """S00048: кубчето зареждаше подразбирането, не стойността от POC."""
        order, _poc = self._poc_for_matrix()
        result = self._patch(
            order.order_line, {U["t_width_mm"]: 100.0, U["t_board"]: "White B"}
        )
        self.assertEqual(result["values"][U["t_width_mm"]], 300.0)
        self.assertEqual(result["values"][U["t_material"]], "hdpe")
        self.assertEqual(result["values"][U["t_board"]], BOARD)
        # POC ги управлява — в конфигуратора са заключени
        self.assertIn(U["t_width_mm"], result["locked"])
        self.assertIn(U["t_board"], result["locked"])
        # само матрицата го има — остава свободен
        self.assertNotIn(U["t_trim_waste"], result["values"])
        self.assertNotIn(U["t_trim_waste"], result["locked"])

    def test_without_the_line_nothing_is_imposed(self):
        self._poc_for_matrix()
        result = self._patch(False, {U["t_width_mm"]: 100.0})
        self.assertEqual(result, {"values": {}, "locked": []})

    def test_a_line_without_poc_is_left_to_the_vertical(self):
        order = self._make_order()
        result = self._patch(order.order_line, {U["t_width_mm"]: 100.0})
        self.assertEqual(result, {"values": {}, "locked": []})

    def test_every_poc_choice_loads_its_parameters_once(self):
        """Избор от POC зарежда своите, както избор на екрана — само ако е друг.

        Не само материалът: всеки избор, който POC управлява.
        """
        calls = []

        def vertical(definition, definition_id, changed_key, params):
            calls.append(changed_key)
            if changed_key == U["t_material"]:
                return {"values": {U["t_trim_waste"]: 0.09}, "locked": []}
            if changed_key == U["t_board"]:
                return {
                    "values": {U["t_length_mm"]: 1.0},
                    "locked": [U["t_trim_waste"]],
                }
            return {"values": {}, "locked": []}

        order, _poc = self._poc_for_matrix()
        line = order.order_line
        with patch.object(
            base_definition.DesignParamDefinition, "get_param_patch", vertical
        ):
            other = self._patch(
                line, {U["t_material"]: "ldpe", U["t_board"]: "White B"}
            )
            calls_other = list(calls)
            calls.clear()
            same = self._patch(
                line,
                {U["t_material"]: "hdpe", U["t_board"]: BOARD, U["t_trim_waste"]: 0.08},
            )
        self.assertEqual(calls_other, [False, U["t_material"], U["t_board"]])
        self.assertEqual(other["values"][U["t_trim_waste"]], 0.09)
        self.assertIn(U["t_trim_waste"], other["locked"])  # заключено от избора
        # POC печели пред заредените: дължината е негова
        self.assertEqual(other["values"][U["t_length_mm"]], 500.0)
        self.assertEqual(calls, [False])  # същият избор не презарежда
        self.assertNotIn(U["t_trim_waste"], same["values"])  # ръчното 0,08 оцелява

    def test_the_fixed_lot_stops_the_poc_overlay(self):
        """След фиксиране матрицата чете от партидата, не от POC."""
        order, _poc = self._poc_for_matrix()
        order.action_confirm()
        result = self._patch(order.order_line, {U["t_width_mm"]: 450.0})
        self.assertNotIn(U["t_width_mm"], result["values"])
        self.assertNotIn(U["t_width_mm"], result["locked"])

    def test_the_configurator_does_not_open_by_itself_for_poc_products(self):
        """Артикул с шаблон за POC се води през POC на офертата."""
        Line = self.env["sale.order.line"]
        self.product.design_param_definition_id = self.definition
        self.assertIs(
            Line.get_design_definition_for_product(self.product.id)["autoOpen"], False
        )
        plain = self.env["product.product"].create(
            {
                "name": "Plain Matrix Bag",
                "design_param_definition_id": self.definition.id,
            }
        )
        self.assertNotIn("autoOpen", Line.get_design_definition_for_product(plain.id))
