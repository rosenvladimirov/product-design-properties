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
from odoo import fields, models


class MrpWorkorder(models.Model):
    """Работната поръчка чете конфигурацията на MO (ADR sale-order-poc/0010)."""

    _inherit = "mrp.workorder"

    poc_id = fields.Many2one(related="production_id.poc_id", store=True)
    poc_template_id = fields.Many2one(related="production_id.poc_template_id", store=True)
    poc_params = fields.Properties(
        string="Configuration",
        related="production_id.poc_params",
        definition="poc_template_id.param_definition",
        readonly=True,
    )
    poc_summary = fields.Char(
        related="production_id.poc_summary", string="Configuration Summary"
    )
