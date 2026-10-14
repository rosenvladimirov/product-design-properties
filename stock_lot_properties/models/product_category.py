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


class ProductCategory(models.Model):
    _inherit = "product.category"

    # Свойствата на партидата от доставката (нето кг, плавка, сертификат…)
    # са на категорията, не на продукта: важат за всички ламарини наведнъж и
    # не минават през дизайн механизма на матрицата (Росен, 14.10.2026).
    lot_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Lot Parameter Set",
        help="Parameter set that every new lot of a product in this category "
        "receives, e.g. net weight, heat number and 3.1 certificate for sheet "
        "metal. Subcategories without their own set inherit it.",
    )

    def _lot_param_definition(self):
        """Наборът за партидата: собственият или най-близкият на родител."""
        # продукт без категория също стига дотук — празният набор, не грешка
        # (14.10.2026: ensure_one() спираше създаването на всяка такава партида)
        category = self[:1]
        while category:
            if category.lot_param_definition_id:
                return category.lot_param_definition_id
            category = category.parent_id
        return self.env["design.param.definition"]
