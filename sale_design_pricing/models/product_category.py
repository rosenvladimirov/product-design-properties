from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    design_material_markup_percent = fields.Float(
        string="Material Markup (%)",
        help="Override the company default. Inherited by products in this category unless they override it.",
    )
    design_labor_markup_percent = fields.Float(
        string="Labor Markup (%)",
        help="Override the company default. Inherited by products in this category unless they override it.",
    )
