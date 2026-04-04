#  Copyright 2024 Simone Rubino - Aion Tech
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import test_python_expr


class MrpBomLineFormulaTemplate(models.Model):
    _name = "mrp.bom.line.formula.template"
    _description = "BoM Line Quantity Formula Template"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    quantity_formula = fields.Text(
        required=True,
        help="Formula evaluated when generating a production order line.\n\n"
        "Available input variables:\n"
        "- bom_line: the current BoM line\n"
        "- operation: workcenter for current BoM line\n"
        "- product: product of current BoM line\n"
        "- product_uom: UoM of the product\n"
        "- product_uom_qty: quantity of the production order\n"
        "- production: the production order being created\n"
        "- env: Odoo environment (for env.ref(), searches, etc.)\n"
        "- design context keys (width, height, etc.) when available\n\n"
        "Output variables (assign in formula):\n"
        "- result (or quantity): computed quantity (required)\n"
        "- product: override the BoM line product (optional)\n"
        "- uom: override the UoM (optional)\n\n"
        "Example:\n"
        "  result = width * height / 1000000\n"
        "  product = env.ref('my_module.special_product')\n"
        "  uom = env.ref('uom.product_uom_kgm')",
    )

    @api.constrains("quantity_formula")
    def _constrain_quantity_formula(self):
        for template in self:
            if template.quantity_formula:
                error_message = test_python_expr(
                    expr=template.quantity_formula,
                    mode="exec",
                )
                if error_message:
                    raise ValidationError(error_message)
