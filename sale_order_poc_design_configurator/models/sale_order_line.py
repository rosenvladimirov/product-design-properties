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
"""POC е за офертата — конфигураторът не се отваря сам.

Огледалната продажба във фирмата производител няма POC: той е във
фирмата продавач и стига дотук само с дизайн партидата, която е осиновил
(ADR sale-order-poc/0021). Такъв ред е конфигуриран — пазачът преди
процюърмънта не бива да го спира (Солид, 03.10.2026: покупката към
Продакшън не се потвърждаваше, щом вратата носеше шаблон за POC).

При избор на продукт с дизайн дефиниция кубчето се отваря само. Артикул с
шаблон за POC се води през POC на офертата, а до матрицата стига с
поръчката — затова тук конфигураторът не изскача.
"""

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def get_design_definition_for_product(self, product_id):
        result = super().get_design_definition_for_product(product_id)
        product = self.env["product.product"].browse(product_id).exists()
        if result and product.product_tmpl_id.poc_template_id:
            result = {**result, "autoOpen": False}
        return result

    def _poc_is_configured(self):
        return super()._poc_is_configured() or bool(
            self.sudo().design_lot_id.poc_id
        )
