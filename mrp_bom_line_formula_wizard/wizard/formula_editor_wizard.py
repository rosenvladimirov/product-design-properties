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
    "\n"
    "Assign the result to 'quantity'.\n"
    "\n"
    "Example:\n"
    "  quantity = product_uom_qty * 1.05\n"
    "\n"
    "Example with dimensions (requires mrp_bom_formula_lot_dimension):\n"
    "  area = (width / 1000) * (height / 1000)\n"
    "  quantity = area * product_uom_qty"
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
    quantity_formula = fields.Text(
        string="Quantity Formula",
        help=FORMULA_HELP,
    )
    formula_help_text = fields.Text(
        default=FORMULA_HELP,
        readonly=True,
        string="Available Variables",
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
