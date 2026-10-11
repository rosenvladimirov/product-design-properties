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


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_bg_pos_has_poc = fields.Boolean(
        string="Has Production Configuration",
        compute="_compute_l10n_bg_pos_has_poc",
        help="The product has a production configuration template: the Point "
        "of Sale opens the configuration editor for its wholesale lines.",
    )

    @api.depends("poc_template_id")
    def _compute_l10n_bg_pos_has_poc(self):
        for template in self:
            template.l10n_bg_pos_has_poc = bool(template.poc_template_id)

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        if not fields_list:
            return fields_list
        return fields_list + ["l10n_bg_pos_has_poc"]
