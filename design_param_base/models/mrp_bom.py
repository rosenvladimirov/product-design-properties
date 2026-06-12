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
