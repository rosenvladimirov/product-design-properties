from odoo import models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _evaluate_cost_with_params(self, params):
        """Compute material + labor cost for this BoM given a parameter namespace.

        Returns a dict::

            {
                "material_cost": float,
                "labor_cost": float,
                "lines": [{"product_id", "product_name", "qty", "unit_cost", "subtotal"}, ...],
                "operations": [{"workcenter_id", "name", "minutes", "rate_per_hour", "subtotal"}, ...],
            }

        ``params`` is a flat dict of design parameters (lot.design_params merged
        with template-level design properties).
        """
        self.ensure_one()
        breakdown_lines = []
        material_cost = 0.0
        for bom_line in self.bom_line_ids:
            qty = bom_line._evaluate_quantity(params)
            qty_with_loss = qty * (1.0 + (bom_line.loss or 0.0) / 100.0)
            unit_cost = bom_line.product_id.standard_price
            subtotal = qty_with_loss * unit_cost
            material_cost += subtotal
            breakdown_lines.append({
                "product_id": bom_line.product_id.id,
                "product_name": bom_line.product_id.display_name,
                "qty": qty_with_loss,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
            })

        breakdown_ops = []
        labor_cost = 0.0
        for op in self.operation_ids:
            workcenter = op.workcenter_id
            if not workcenter:
                continue
            minutes = op.time_cycle or 0.0
            rate = workcenter.costs_hour or 0.0
            subtotal = (minutes / 60.0) * rate
            labor_cost += subtotal
            breakdown_ops.append({
                "workcenter_id": workcenter.id,
                "name": op.name,
                "minutes": minutes,
                "rate_per_hour": rate,
                "subtotal": subtotal,
            })

        return {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "lines": breakdown_lines,
            "operations": breakdown_ops,
        }
