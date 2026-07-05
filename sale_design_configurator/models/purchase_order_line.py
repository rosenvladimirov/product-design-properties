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


class PurchaseOrderLine(models.Model):
    """PO клон на design_lot пропагацията (по аналог на forced_lot):
    когато procurement-ът от SO се резолва към ПОКУПКА, design лотът минава
    procurement values → PO ред → incoming движение → присвоен лот при получаване.
    """

    _inherit = "purchase.order.line"

    design_lot_id = fields.Many2one(
        "stock.lot",
        string="Design Lot",
        copy=False,
        help="Design lot propagated from the SO procurement; the received "
        "product is assigned this lot on receipt.",
    )

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        vals = super()._prepare_stock_move_vals(
            picking, price_unit, product_uom_qty, product_uom
        )
        if self.design_lot_id:
            vals["design_lot_id"] = self.design_lot_id.id
        return vals

    @api.model
    def _prepare_purchase_order_line_from_procurement(
        self, product_id, product_qty, product_uom, location_dest_id,
        name, origin, company_id, values, po,
    ):
        vals = super()._prepare_purchase_order_line_from_procurement(
            product_id, product_qty, product_uom, location_dest_id,
            name, origin, company_id, values, po,
        )
        if values.get("design_lot_id"):
            vals["design_lot_id"] = values["design_lot_id"]
        return vals
