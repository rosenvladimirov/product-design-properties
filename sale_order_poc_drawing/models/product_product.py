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
from odoo import api, fields, models

from .poc_param import check_drawing_color


class ProductProduct(models.Model):
    _inherit = "product.product"

    # цветът на материала в рисунката — поле, не дума в името (ADR sale-order-poc/0025, т. 5)
    drawing_color = fields.Char(
        help="Colour of this product in the product drawing, as #rrggbb, "
        "e.g. the colour of a board or a decor."
    )

    @api.constrains("drawing_color")
    def _check_drawing_color(self):
        check_drawing_color(self)
