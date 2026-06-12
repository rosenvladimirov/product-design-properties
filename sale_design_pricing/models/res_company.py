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


class ResCompany(models.Model):
    _inherit = "res.company"

    design_material_markup_percent = fields.Float(
        string="Default Material Markup (%)",
        default=50.0,
        help="Default markup applied to material cost when computing list price for design products.",
    )
    design_labor_markup_percent = fields.Float(
        string="Default Labor Markup (%)",
        default=50.0,
        help="Default markup applied to labor cost when computing list price for design products.",
    )

    @api.model
    def _init_design_markups(self):
        """Backfill 50/50 markups on companies that don't have a value yet.

        Called once from data/ir_config_parameter_data.xml during module
        install. Field default=50.0 only applies to NEW records — existing
        companies (e.g. base.main_company created by `base`) get the column
        added with 0/0 on schema migration, so we backfill them here.
        Idempotent: only writes when the field is still 0.
        """
        for company in self.search([]):
            vals = {}
            if not company.design_material_markup_percent:
                vals["design_material_markup_percent"] = 50.0
            if not company.design_labor_markup_percent:
                vals["design_labor_markup_percent"] = 50.0
            if vals:
                company.write(vals)
