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
from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _prepare_mo_vals(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
        bom,
    ):
        """MO без POC в процюърмънта го взема от дизайн партидата.

        Фирмата производител получава поръчката от огледалната продажба —
        там POC няма, но партидата е същата и носи ``poc_id`` от
        осиновяването. Пълна връзка: оттук MO следва POC като MO на
        продаващата фирма — лот, резюме, параметри, преизчисляване.
        """
        if not values.get("poc_id") and values.get("design_lot_id"):
            lot = self.env["stock.lot"].sudo().browse(values["design_lot_id"])
            if lot.poc_id:
                values = dict(values, poc_id=lot.poc_id.id)
        return super()._prepare_mo_vals(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
            bom,
        )
