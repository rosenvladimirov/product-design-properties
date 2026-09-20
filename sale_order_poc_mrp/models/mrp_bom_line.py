# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    force_mts = fields.Boolean(
        string="Always Take from Stock",
        help="The component is taken from stock even if its routes would "
        "manufacture it for the configuration (e.g. granulate, packaging).",
    )
