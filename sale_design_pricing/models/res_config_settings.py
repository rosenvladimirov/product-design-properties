from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    design_material_markup_percent = fields.Float(
        related="company_id.design_material_markup_percent",
        readonly=False,
    )
    design_labor_markup_percent = fields.Float(
        related="company_id.design_labor_markup_percent",
        readonly=False,
    )
