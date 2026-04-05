# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    design_definition_ids = fields.Many2many(
        "design.param.definition",
        string="Active Design Definitions",
        help=(
            "Design parameter definitions available for this company. "
            "If empty, all are available."
        ),
    )
