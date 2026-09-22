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
"""POC храни матрицата — едно към едно по име (ADR sale-order-poc/0019)."""

from odoo.tests import tagged

from .common import BOARD, MatrixPocCommon, U


@tagged("post_install", "-at_install")
class TestMatrixParams(MatrixPocCommon):
    def test_context_is_the_matrix_plus_the_poc(self):
        _order, poc = self._poc_for_matrix()
        context = poc._poc_matrix_context()
        self.assertEqual(context["t_width_mm"], 300.0)  # от POC
        self.assertEqual(context["t_length_mm"], 500.0)  # от POC
        self.assertEqual(context["t_material"], "hdpe")  # ключът на избора
        self.assertEqual(context["t_trim_waste"], 0.05)  # само матрицата го има

    def test_only_matching_names_are_read(self):
        """Кодовете, които матрицата няма, не влизат; разделителят — също."""
        _order, poc = self._poc_for_matrix()
        context = poc._poc_matrix_context()
        self.assertNotIn("t_thickness_um", context)
        self.assertNotIn("t_density", context)
        self.assertNotIn("Sizes", context)
        self.assertEqual(
            set(context),
            {
                "t_width_mm",
                "t_length_mm",
                "t_material",
                "t_board",
                "t_trim_waste",
                "t_printer",
            },
        )

    def test_a_variant_becomes_the_raw_key_of_the_selection(self):
        _order, poc = self._poc_for_matrix()
        self.assertEqual(poc._poc_matrix_context()["t_board"], BOARD)

    def test_an_unknown_record_is_skipped_loudly(self):
        """Вариант, който изборът не познава, не влиза — и се вижда в лога."""
        other = self.env["product.product"].create({"name": "Unknown Board"})
        _order, poc = self._poc_for_matrix(t_board=other.id)
        with self.assertLogs(
            "odoo.addons.sale_order_poc_design_matrix.models.sale_order_poc", "WARNING"
        ) as logs:
            context = poc._poc_matrix_context()
        self.assertIsNone(context["t_board"])  # подразбирането на матрицата
        self.assertIn("t_board", logs.output[0])

    def test_a_record_never_lands_in_a_plain_parameter(self):
        """Печатарят (запис) срещу текстов параметър няма съответствие."""
        _order, poc = self._poc_for_matrix(t_printer=self.printer.id)
        with self.assertLogs(
            "odoo.addons.sale_order_poc_design_matrix.models.sale_order_poc", "WARNING"
        ):
            context = poc._poc_matrix_context()
        self.assertFalse(context["t_printer"])

    def test_an_empty_record_is_no_value(self):
        """Незададен печатар не е „запис без съответствие“ — просто няма стойност."""
        _order, poc = self._poc_for_matrix()
        with self.assertNoLogs(
            "odoo.addons.sale_order_poc_design_matrix.models.sale_order_poc", "WARNING"
        ):
            context = poc._poc_matrix_context()
        self.assertIsNone(context["t_printer"])

    def test_the_draft_has_no_lot(self):
        _order, poc = self._poc_for_matrix()
        self.assertFalse(poc.lot_id)

    def test_the_confirmed_lot_carries_the_matrix(self):
        order, poc = self._poc_for_matrix()
        order.action_confirm()
        lot = poc.lot_id
        self.assertTrue(lot)
        self.assertEqual(lot.design_param_definition_id, self.definition)
        values = lot.design_params._values
        self.assertEqual(values[U["t_width_mm"]], 300.0)
        self.assertEqual(values[U["t_material"]], "hdpe")
        self.assertEqual(values[U["t_board"]], BOARD)
        self.assertEqual(values[U["t_trim_waste"]], 0.05)

    def test_matrix_values_of_the_lot_survive_a_second_pass(self):
        """Ръчното в партидата оцелява; POC пише само своите."""
        order, poc = self._poc_for_matrix()
        order.action_confirm()
        lot = poc.lot_id
        lot.design_params = {
            **lot.design_params._values,
            U["t_trim_waste"]: 0.07,
            U["t_width_mm"]: 1.0,
        }
        poc._poc_ensure_lot()
        values = lot.design_params._values
        self.assertEqual(values[U["t_trim_waste"]], 0.07)
        self.assertEqual(values[U["t_width_mm"]], 300.0)

    def test_a_product_without_a_definition_is_left_alone(self):
        self.bom.design_param_definition_id = False
        order, poc = self._poc_for_matrix()
        self.assertIsNone(poc._poc_matrix_context())
        order.action_confirm()
        self.assertTrue(poc.lot_id)
        self.assertFalse(poc.lot_id.design_param_definition_id)

    def test_the_sale_configurator_is_not_needed(self):
        """Демакс и заводи без конфигуратора: модулът не го тегли."""
        Module = self.env["ir.module.module"]
        todo = Module.search([("name", "=", "sale_order_poc_design_matrix")])
        closure = Module.browse()
        while todo:
            closure |= todo
            todo = todo.dependencies_id.depend_id - closure
        self.assertIn("mrp_design_matrix", closure.mapped("name"))
        self.assertNotIn("sale_design_configurator", closure.mapped("name"))
