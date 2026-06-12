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
"""
E2E тестове за операционните формули: продължителност, skip и
закачане на консумирания материал към workorder-а.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestOperationFormula(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workcenter = cls.env["mrp.workcenter"].create(
            {"name": "Formula WC", "time_efficiency": 100}
        )
        cls.parent = cls.env["product.product"].create(
            {"name": "Op Formula Parent", "is_storable": True}
        )
        cls.component = cls.env["product.product"].create(
            {"name": "Op Formula Component", "is_storable": True}
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.parent.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )
        cls.env["mrp.bom.line"].create(
            {
                "bom_id": cls.bom.id,
                "product_id": cls.component.id,
                "product_qty": 1.0,
            }
        )
        cls.operation = cls.env["mrp.routing.workcenter"].create(
            {
                "name": "Formula Operation",
                "bom_id": cls.bom.id,
                "workcenter_id": cls.workcenter.id,
                "time_cycle_manual": 30.0,
            }
        )

    def _set_formula(self, formula):
        template = self.env["mrp.bom.line.formula.template"].create(
            {"name": "op-formula %s" % len(formula), "quantity_formula": formula}
        )
        self.operation.formula_template_id = template

    def _make_mo(self, qty=2.0, confirm=True):
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.parent.id,
                "bom_id": self.bom.id,
                "product_qty": qty,
            }
        )
        if confirm:
            mo.action_confirm()
        return mo

    def test_duration_formula(self):
        """result = минути → duration_expected на workorder-а."""
        self._set_formula("result = 15 * product_qty")
        mo = self._make_mo(qty=3.0)
        wo = mo.workorder_ids.filtered(
            lambda w: w.operation_id == self.operation
        )
        self.assertEqual(len(wo), 1)
        self.assertAlmostEqual(wo.duration_expected, 45.0)

    def test_duration_relative_to_standard(self):
        """duration е инициализирана със стандарта — формулата може
        да я коригира релативно."""
        self._set_formula("result = duration + 10")
        mo = self._make_mo(qty=1.0)
        wo = mo.workorder_ids.filtered(
            lambda w: w.operation_id == self.operation
        )
        self.assertGreater(wo.duration_expected, 10.0)

    def test_skip_drops_workorder(self):
        """skip = True → операцията изчезва от MO-то при потвърждаване."""
        self._set_formula("skip = product_qty < 5")
        mo = self._make_mo(qty=2.0)
        self.assertFalse(
            mo.workorder_ids.filtered(
                lambda w: w.operation_id == self.operation
            ),
            "skip=True must drop the work order",
        )
        mo_big = self._make_mo(qty=8.0)
        self.assertTrue(
            mo_big.workorder_ids.filtered(
                lambda w: w.operation_id == self.operation
            )
        )

    def test_collect_materials(self):
        """collect_materials = True → суровините се консумират тук."""
        if "workorder_id" not in self.env["stock.move"]._fields:
            self.skipTest("stock.move has no workorder_id field")
        self._set_formula("result = 20\ncollect_materials = True")
        mo = self._make_mo(qty=1.0)
        wo = mo.workorder_ids.filtered(
            lambda w: w.operation_id == self.operation
        )
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertEqual(move.workorder_id, wo)

    def test_materials_by_product(self):
        """materials = [продукт] → закача само неговите move-ове."""
        if "workorder_id" not in self.env["stock.move"]._fields:
            self.skipTest("stock.move has no workorder_id field")
        self.env["ir.model.data"].create(
            {
                "name": "op_formula_component",
                "module": "mrp_operation_formula_template",
                "model": "product.product",
                "res_id": self.component.id,
            }
        )
        self._set_formula(
            "result = 20\n"
            "materials = [env.ref("
            "'mrp_operation_formula_template.op_formula_component')]"
        )
        mo = self._make_mo(qty=1.0)
        wo = mo.workorder_ids.filtered(
            lambda w: w.operation_id == self.operation
        )
        move = mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.component
        )
        self.assertEqual(move.workorder_id, wo)

    def test_invalid_duration_keeps_standard(self):
        """Нечислов резултат → warning + стандартната продължителност."""
        self._set_formula("result = 'oops'")
        with self.assertLogs(level="WARNING"):
            mo = self._make_mo(qty=1.0)
        wo = mo.workorder_ids.filtered(
            lambda w: w.operation_id == self.operation
        )
        self.assertEqual(len(wo), 1)
        self.assertGreater(wo.duration_expected, 0.0)
