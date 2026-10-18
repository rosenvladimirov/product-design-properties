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

from ..tools import stored_properties


class StockLot(models.Model):
    _inherit = "stock.lot"

    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Parameter Set",
    )
    design_params = fields.Properties(
        "Design Parameters",
        definition="design_param_definition_id.full_design_params_definition",
        copy=True,
    )

    def _get_stored_properties(self, field_name="design_params"):
        """Суровият записан речник на поле Properties на партидата.

        Общият помощник за всеки, който СРАВНЯВА, СЪВПАДА или КОПИРА
        параметрите на партида: дава ключа на избора (не етикета) и
        ``0``/``""`` такива, каквито са записани — както ``lot.design_params``
        в 18.0. Подробности в ``stock_lot_properties.tools.stored_properties``.
        """
        self.ensure_one()
        return stored_properties(self, field_name)

    @api.model_create_multi
    def create(self, vals_list):
        # Партида без набор взима набора на категорията на продукта — така
        # всяка нова пачка ламарина идва с полетата си (нето кг, плавка,
        # сертификат 3.1). Изрично подаден набор не се пипа; продукт със свой
        # дизайн набор (матрицата) също се пропуска.
        for vals in vals_list:
            if vals.get("design_param_definition_id") or not vals.get("product_id"):
                continue
            product = self.env["product.product"].browse(vals["product_id"])
            if getattr(product, "design_param_definition_id", False):
                continue
            definition = product.categ_id._lot_param_definition()
            if definition:
                vals["design_param_definition_id"] = definition.id
        return super().create(vals_list)
