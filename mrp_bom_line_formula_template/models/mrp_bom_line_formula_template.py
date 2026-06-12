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
        help="Python code executed while a manufacturing order builds its "
        "component moves. Write the computed amount into 'result' "
        "('quantity' is also accepted for backward compatibility).\n\n"
        "The code runs with this context:\n"
        "  bom_line - the mrp.bom.line being exploded\n"
        "  operation - the linked work-center operation, or False\n"
        "  product / product_uom - component product and its unit\n"
        "  product_uom_qty - quantity ordered on the MO\n"
        "  production - the mrp.production record\n"
        "  env - Odoo environment (env.ref(), searches, ...)\n"
        "  design parameters (width, height, ...) as flat variables, "
        "when a design context is attached\n\n"
        "Optional overrides the code may set:\n"
        "  skip - set True to drop this BoM line from the MO entirely\n"
        "  product - replacement component (recordset)\n"
        "  uom - replacement unit of measure (recordset)\n\n"
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
