# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    design_definition_ids = fields.Many2many(
        "design.param.definition",
        related="company_id.design_definition_ids",
        readonly=False,
        string="Active Design Definitions",
    )
