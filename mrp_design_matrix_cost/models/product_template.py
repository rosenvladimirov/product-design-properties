# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Теолино-style надценки: продажната цена се извежда от себестойността с
    # РАЗЛИЧЕН процент за материали и за труд. Default 0 → продажна = себестойност.
    material_markup_percent = fields.Float(
        string="Material Markup (%)",
        help="Markup applied on the material cost to suggest a sale price "
        "(separate from labour). 0 = no markup.",
    )
    labor_markup_percent = fields.Float(
        string="Labour Markup (%)",
        help="Markup applied on the labour cost to suggest a sale price "
        "(separate from materials). 0 = no markup.",
    )
