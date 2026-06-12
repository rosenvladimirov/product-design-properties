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
