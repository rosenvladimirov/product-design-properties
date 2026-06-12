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
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import test_python_expr

# Technical reference shown verbatim in the wizard — not translated.
FORMULA_HELP = """\
Available variables:
  bom_line         - the current BoM line
  production       - the manufacturing order
  product          - product of this BoM line
  product_uom      - UoM of the product
  product_uom_qty  - quantity from the MO
  operation        - routing workcenter (if set)
  env              - Odoo environment (env.ref(), searches)

Design context (when design matrix is active):
  width, height, thickness - lot dimensions
  + all T1 geometry outputs as flat variables
  + all design_params from the lot
  design_context   - full context dict

Output variables (assign in formula):
  result           - computed quantity (or 'quantity')
  product          - override product (optional)
  uom              - override UoM (optional)
  skip             - True drops this BoM line from the MO (optional)

Examples:
  result = product_uom_qty * 1.05

  # Area-based with design dimensions
  result = (width / 1000) * (height / 1000)

  # Override product based on param
  result = 1
  if construction == 'glass':
      product = env.ref('my_module.glass_panel')
      uom = env.ref('uom.product_uom_unit')"""


class FormulaEditorWizard(models.TransientModel):
    _name = "mrp.bom.line.formula.wizard"
    _description = "BoM Line Quantity Formula Editor"

    bom_line_id = fields.Many2one(
        "mrp.bom.line",
        required=True,
        readonly=True,
    )
    product_name = fields.Char(
        readonly=True,
        string="Component",
    )
    formula_template_id = fields.Many2one(
        "mrp.bom.line.formula.template",
        string="Load from Template",
    )
    quantity_formula = fields.Text(
        string="Formula",
        help=FORMULA_HELP,
    )
    formula_help_text = fields.Text(
        default=FORMULA_HELP,
        readonly=True,
        string="Reference",
    )

    @api.constrains("quantity_formula")
    def _constrain_quantity_formula(self):
        for wiz in self:
            if wiz.quantity_formula:
                error = test_python_expr(
                    expr=wiz.quantity_formula,
                    mode="exec",
                )
                if error:
                    raise ValidationError(error)

    @api.onchange("formula_template_id")
    def _onchange_formula_template_id(self):
        if self.formula_template_id:
            self.quantity_formula = self.formula_template_id.quantity_formula

    def action_apply(self):
        """Write the formula back to the BoM line."""
        self.ensure_one()
        self.bom_line_id.quantity_formula = self.quantity_formula or False
        return {"type": "ir.actions.act_window_close"}

    def action_clear(self):
        """Clear the formula from the BoM line."""
        self.ensure_one()
        self.quantity_formula = False
        self.bom_line_id.quantity_formula = False
        return {"type": "ir.actions.act_window_close"}
