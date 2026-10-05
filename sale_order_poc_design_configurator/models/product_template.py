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


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # една бройка — един ред — една дизайн партида (Солид, 05.10.2026, т. 15)
    poc_one_unit_per_line = fields.Boolean(
        string="One Unit per Line",
        help="Each unit is made to its own configuration and design lot. A "
        "quantity above one splits the order line into lines of one unit; "
        "the new lines copy the configuration, which can then be changed "
        "line by line. On a confirmed order the new line gets the next "
        "design lot and its own purchase or manufacturing order line.",
    )
