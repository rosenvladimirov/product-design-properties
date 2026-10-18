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
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    design_material_markup_percent = fields.Float(
        string="Material Markup (%)",
        help="Override the category/company default markup applied to material cost.",
    )
    design_labor_markup_percent = fields.Float(
        string="Labor Markup (%)",
        help="Override the category/company default markup applied to labor cost.",
    )

    effective_material_markup_percent = fields.Float(
        compute="_compute_effective_markups",
    )
    effective_labor_markup_percent = fields.Float(
        compute="_compute_effective_markups",
    )

    @api.depends(
        "design_material_markup_percent",
        "design_labor_markup_percent",
        "categ_id.design_material_markup_percent",
        "categ_id.design_labor_markup_percent",
        "company_id.design_material_markup_percent",
        "company_id.design_labor_markup_percent",
    )
    def _compute_effective_markups(self):
        for tmpl in self:
            company = tmpl.company_id or self.env.company
            tmpl.effective_material_markup_percent = (
                tmpl.design_material_markup_percent
                or tmpl.categ_id.design_material_markup_percent
                or company.design_material_markup_percent
            )
            tmpl.effective_labor_markup_percent = (
                tmpl.design_labor_markup_percent
                or tmpl.categ_id.design_labor_markup_percent
                or company.design_labor_markup_percent
            )
