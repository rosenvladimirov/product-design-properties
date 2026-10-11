# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Грешка в ZEN таблица се записва в лога, цената не пада (липсващият _logger до 18.0.1.3.4)."""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper


@tagged("post_install", "-at_install")
class TestTmEvaluate(TransactionCase):
    def test_failing_tables_are_logged_not_raised(self):
        product = self.env["product.product"].create({"name": "Priced item"})
        table = {"nodes": [], "edges": []}
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "constraint_table": table,
                "geometry_table": table,
                "material_table": table,
                "operation_table": table,
            }
        )
        with patch.object(ZenWrapper, "evaluate", side_effect=ValueError("broken table")), self.assertLogs(
            "odoo.addons.sale_design_pricing.models.mrp_bom", level="WARNING"
        ) as logs:
            t0, ctx, coeffs, adhoc, t3 = bom._tm_evaluate({"width": 1000})
        self.assertEqual(len(logs.output), 4)
        self.assertEqual((t0, coeffs, adhoc, t3), ([], {}, [], None))
        self.assertEqual(ctx, {"width": 1000})
