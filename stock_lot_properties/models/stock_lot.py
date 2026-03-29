# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Parameter Set",
    )
    design_params = fields.Properties(
        "Design Parameters",
        definition="design_param_definition_id.full_design_params_definition",
        copy=True,
    )
