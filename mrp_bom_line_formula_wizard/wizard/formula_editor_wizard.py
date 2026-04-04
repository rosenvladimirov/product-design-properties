# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import test_python_expr

FORMULA_HELP = _(
    "Available variables:\n"
    "  bom_line         - the current BoM line\n"
    "  production       - the manufacturing order\n"
    "  product          - product of this BoM line\n"
    "  product_uom      - UoM of the product\n"
    "  product_uom_qty  - quantity from the MO\n"
    "  operation        - routing workcenter (if set)\n"
    "  env              - Odoo environment (env.ref(), searches)\n"
    "\n"
    "Design context (when design matrix is active):\n"
    "  width, height, thickness - lot dimensions\n"
    "  + all T1 geometry outputs as flat variables\n"
    "  + all design_params from the lot\n"
    "  design_context   - full context dict\n"
    "\n"
    "Output variables (assign in formula):\n"
    "  result           - computed quantity (or 'quantity')\n"
    "  product          - override product (optional)\n"
    "  uom              - override UoM (optional)\n"
    "\n"
    "Examples:\n"
    "  result = product_uom_qty * 1.05\n"
    "\n"
    "  # Area-based with design dimensions\n"
    "  result = (width / 1000) * (height / 1000)\n"
    "\n"
    "  # Override product based on param\n"
    "  result = 1\n"
    "  if construction == 'glass':\n"
    "      product = env.ref('my_module.glass_panel')\n"
    "      uom = env.ref('uom.product_uom_unit')"
)


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
