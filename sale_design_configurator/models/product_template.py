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

    # търгуваната врата получава номер при продажбата, не при приемането
    design_lot_on_confirm = fields.Boolean(
        string="Lot at Sale Confirmation",
        help="Confirming a sales order gives the line a new lot, named by the "
        "product's lot sequence, unless the line already has a design lot. The "
        "lot travels with the procurement to the purchase receipt, the "
        "manufacturing order and the delivery. Only for lines procured to "
        "order: a product sold from stock keeps the lot of its receipt.",
    )
