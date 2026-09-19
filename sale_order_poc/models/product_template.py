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


class ProductTemplate(models.Model):
    _inherit = "product.template"

    poc_template_id = fields.Many2one(
        "sale.order.poc.template",
        string="Production Configuration Template",
        domain=[("usage", "=", "main")],
        help="A sale of this product needs a production configuration made "
        "from this template.",
    )
    # константите на продукта в същото пространство от имена; копират се в
    # конфигурацията при раждането ѝ, формулите виждат само нея
    poc_default_params = fields.Properties(
        string="Configuration Defaults",
        definition="poc_template_id.param_definition",
        copy=True,
    )
