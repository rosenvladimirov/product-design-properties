# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Parameter Set",
        help=(
            "Defines which design parameters are available "
            "for lots produced with this BoM."
        ),
    )
