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
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PocCommon


@tagged("post_install", "-at_install")
class TestPocParams(PocCommon):
    def test_defaults_are_written_including_zero(self):
        """Подразбиранията от речника се пишат изрично — и нулата.

        ORM прилага само истинно подразбиране от схемата.
        """
        poc = self._make_poc()
        values = poc._poc_values()
        self.assertEqual(values["t_density"], 0.92)
        self.assertEqual(values["t_waste_pct"], 0)
        self.assertIsNot(values["t_waste_pct"], False)
        self.assertEqual(values["t_material"], "ldpe")
        self.assertIsNone(values["t_width_mm"])

    def test_reader_returns_keys_and_records(self):
        """Селекцията е ключ, таговете — списък ключове, m2o — запис.

        Мутация: четене през record.params[k] дава етикета 'LDPE' и низ за
        таговете — тестът пада.
        """
        poc = self._make_poc()
        poc._poc_set_params(
            {"t_material": "hdpe", "t_colors": ["red", "blue"], "t_printer": self.printer}
        )
        values = poc._poc_values()
        self.assertEqual(values["t_material"], "hdpe")
        self.assertEqual(values["t_colors"], ["red", "blue"])
        self.assertEqual(values["t_printer"], self.printer)
        # за сравнение: стандартният достъп на Odoo връща етикета
        self.assertEqual(poc.params["t_material"], "HDPE")

    def test_writer_keeps_other_keys(self):
        """Частичен запис не губи другите стойности, включително записа.

        Запис на dict в Properties заменя всичко; писачът слива.
        """
        poc = self._make_poc()
        poc._poc_set_params({"t_printer": self.printer, "t_width_mm": 100.0})
        poc._poc_set_params({"t_length_mm": 200.0})
        values = poc._poc_values()
        self.assertEqual(values["t_printer"], self.printer)
        self.assertEqual(values["t_width_mm"], 100.0)
        self.assertEqual(values["t_length_mm"], 200.0)
        self.assertEqual(values["t_density"], 0.92)

    def test_missing_inputs_leave_output_empty(self):
        """Докато входовете липсват, изчисленото е празно, не грешка."""
        poc = self._make_poc()
        values = poc._poc_values()
        self.assertIsNone(values["t_weight_g"])
        self.assertIsNone(values["t_weight_gross_g"])
        self.assertFalse(poc.summary)

    def test_derived_values_and_summary(self):
        """300×500 мм, 20 µm, 0,92 → 5,52 g; бруто при 0 % фира е същото."""
        poc = self._fill(self._make_poc())
        values = poc._poc_values()
        self.assertAlmostEqual(values["t_weight_g"], 5.52)
        self.assertAlmostEqual(values["t_weight_gross_g"], 5.52)
        self.assertEqual(poc.summary, "300x500/20")
        self.assertEqual(poc.param_origins.get("t_weight_g"), "formula")

    def test_change_of_input_recomputes(self):
        poc = self._fill(self._make_poc())
        poc.write({"params": {**poc.params._values, "t_waste_pct": 10.0}})
        self.assertAlmostEqual(poc._poc_values()["t_weight_gross_g"], 6.072)

    def test_manual_override_survives_recompute(self):
        """Ръчна стойност при allow_manual остава, докато не се върне."""
        poc = self._fill(self._make_poc())
        poc.write({"params": {**poc.params._values, "t_weight_g": 7.0}})
        self.assertEqual(poc.param_origins["t_weight_g"], "manual")
        self.assertEqual(poc.manual_params, "Bag Weight")
        self._fill(poc, width=400.0)
        values = poc._poc_values()
        self.assertEqual(values["t_weight_g"], 7.0)
        # брутото се смята от ръчната стойност
        self.assertAlmostEqual(values["t_weight_gross_g"], 7.0)
        poc.action_reset_to_formula()
        self.assertAlmostEqual(poc._poc_values()["t_weight_g"], 7.36)
        self.assertFalse(poc.manual_params)

    def test_computed_without_allow_manual_cannot_be_edited(self):
        poc = self._fill(self._make_poc())
        with self.assertRaises(UserError):
            poc.write({"params": {**poc.params._values, "t_weight_gross_g": 1.0}})

    def test_formula_error_raises(self):
        """Грешка във формула без allow_fallback дава UserError."""
        line = self.template.line_ids.filtered(
            lambda line: line.param_id == self.p_weight_gross
        )
        line.formula = "result = t_weight_g / 0"
        with self.assertRaises(UserError):
            self._fill(self._make_poc())

    def test_formula_error_with_fallback_keeps_value(self):
        """При allow_fallback стойността остава и в чатъра има бележка."""
        poc = self._fill(self._make_poc())
        line = self.template.line_ids.filtered(
            lambda line: line.param_id == self.p_weight_gross
        )
        line.write({"formula": "result = t_weight_g / 0", "allow_fallback": True})
        messages = len(poc.message_ids)
        poc.action_compute()
        self.assertAlmostEqual(poc._poc_values()["t_weight_gross_g"], 5.52)
        self.assertGreater(len(poc.message_ids), messages)

    def test_temporary_variable_does_not_leak(self):
        """Временна променлива на една формула не се вижда в друга."""
        line = self.template.line_ids.filtered(
            lambda line: line.param_id == self.p_weight
        )
        line.formula = "t_waste_pct = 50\nresult = 1.0"
        poc = self._fill(self._make_poc())
        # брутото вижда истинската фира 0, не 50 от чуждата формула
        self.assertAlmostEqual(poc._poc_values()["t_weight_gross_g"], 1.0)

    def test_product_defaults_apply(self):
        """Константите на продукта влизат при раждането на конфигурацията."""
        self.product.product_tmpl_id.poc_default_params = {"t_thickness_um": 35.0}
        poc = self._make_poc()
        self.assertEqual(poc._poc_values()["t_thickness_um"], 35.0)
