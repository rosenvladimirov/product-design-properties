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
from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    # Ролята на атрибута в дизайн-конфигуратора. Данни, не код: универсалният
    # engine НЕ знае индустриални конвенции за имена (преди класифицираше по
    # кирилски префикси „Цвят*"/„Покритие*" — врати-специфично). Клиентският
    # data модул сетва ролята (Solid: loader-ът мигрира по префикс при -u).
    design_role = fields.Selection(
        [("color", "Color"), ("coating", "Coating"), ("motif", "Motif")],
        string="Design Role",
        help="How the design configurator treats this attribute: "
        "'Color' attributes drive the variant colour picker; 'Coating' "
        "attributes group colours by finish; 'Motif' attributes swap the "
        "3D slab geometry. Empty = not used by the configurator.",
    )
