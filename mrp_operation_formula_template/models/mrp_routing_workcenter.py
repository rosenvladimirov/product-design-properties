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
import logging

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    formula_template_id = fields.Many2one(
        "mrp.bom.line.formula.template",
        string="Operation Formula Template",
        help="Python code executed when the manufacturing order builds its "
        "work orders. Outputs the code may set:\n"
        "  result (or duration) - expected duration in minutes\n"
        "  skip - True drops this operation's work order from the MO\n"
        "  collect_materials - True assigns all still-unassigned raw moves "
        "to this work order\n"
        "  materials - list of products whose raw moves are consumed here\n\n"
        "Context: operation, workcenter, production, workorder, product, "
        "product_qty, duration (standard value), env, and the design "
        "parameters (width, height, ...) when a design lot is attached.",
    )
    operation_formula = fields.Text(
        compute="_compute_operation_formula",
        store=True,
        readonly=True,
    )

    @api.depends("formula_template_id", "formula_template_id.quantity_formula")
    def _compute_operation_formula(self):
        for operation in self:
            operation.operation_formula = (
                operation.formula_template_id.quantity_formula or False
            )

    # ── Formula evaluation (огледало на BoM-line ядрото, но за операции) ──

    def _operation_formula_values(
        self, production, workorder=False, default_duration=0.0
    ):
        """Build the evaluation context for an operation formula."""
        self.ensure_one()
        values = {
            "operation": self,
            "workcenter": self.workcenter_id,
            "production": production or False,
            "workorder": workorder or False,
            "product": production.product_id if production else False,
            "product_qty": production.product_qty if production else 0.0,
            "product_uom_qty": production.product_qty if production else 0.0,
            # начална стойност = стандартната продължителност;
            # формулата я презаписва (duration = ... / result = ...)
            "duration": default_duration,
            "env": self.env,
        }
        # T3 интеграция: design контекстът на произвеждания лот (когато
        # mrp_design_matrix е инсталиран) влиза като плоски променливи
        lot = production.lot_producing_id if production else False
        if lot and hasattr(lot, "_get_design_context"):
            ctx = lot._get_design_context()
            if ctx:
                values["design_context"] = ctx
                values.update(ctx)
        return values

    def _eval_operation_formula(
        self, production, workorder=False, default_duration=0.0
    ):
        """Evaluate the operation formula.

        Returns ``None`` when no formula is set, otherwise a dict::

            {
                "skip": bool,                  # маха workorder-а изцяло
                "duration": float,             # минути (result/duration)
                "collect_materials": bool,     # събери свободните суровини
                "materials": list,             # продукти, консумирани тук
            }
        """
        self.ensure_one()
        formula = self.operation_formula
        if not formula:
            return None

        values = self._operation_formula_values(
            production, workorder=workorder, default_duration=default_duration
        )
        safe_eval(
            formula,
            globals_dict=values,
            mode="exec",
            nocopy=True,
        )

        if values.get("skip"):
            return {"skip": True, "duration": 0.0}

        duration = values.get("result", values.get("duration", default_duration))
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            _logger.warning(
                "Operation formula of %s returned a non-numeric duration "
                "(%r); keeping the standard duration.",
                self.display_name,
                duration,
            )
            duration = default_duration

        result = {"skip": False, "duration": duration}
        if values.get("collect_materials"):
            result["collect_materials"] = True
        if values.get("materials"):
            result["materials"] = values["materials"]
        return result
