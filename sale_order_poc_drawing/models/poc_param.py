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
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def check_drawing_color(records):
    """Цветът на рисунката е ``#rrggbb`` или празен."""
    for record in records:
        if record.drawing_color and not HEX_RE.match(record.drawing_color):
            raise ValidationError(
                records.env._(
                    "The drawing colour %(color)s must be #rrggbb.",
                    color=record.drawing_color,
                )
            )


class SaleOrderPocParamOption(models.Model):
    _inherit = "sale.order.poc.param.option"

    # цветът на опцията в рисунката: v["<код>__color"] (ADR sale-order-poc/0025, т. 5)
    drawing_color = fields.Char(
        help="Colour of this option in the product drawing, as #rrggbb."
    )

    @api.constrains("drawing_color")
    def _check_drawing_color(self):
        check_drawing_color(self)
