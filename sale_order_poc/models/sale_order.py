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


class SaleOrder(models.Model):
    _inherit = "sale.order"

    poc_ids = fields.One2many("sale.order.poc", "order_id")
    poc_count = fields.Integer(compute="_compute_poc_count")

    def _compute_poc_count(self):
        for order in self:
            order.poc_count = len(order.poc_ids)

    def copy(self, default=None):
        new_orders = super().copy(default)
        for order, new_order in zip(self, new_orders, strict=True):
            order._poc_copy_to(new_order)
        return new_orders

    def _poc_copy_to(self, new_order):
        """Всеки ред с конфигурация получава копие ѝ, без лота.

        Редовете се съвпадат по продукт и поредност: копието на поръчката
        пропуска някои редове (напр. авансовите), затова позицията не става.
        """
        unmatched = new_order.order_line
        for line in self.order_line.filtered("poc_id"):
            match = unmatched.filtered(
                lambda new_line, line=line: new_line.product_id == line.product_id
                and new_line.sequence == line.sequence
            )[:1]
            if match:
                line.poc_id.copy({"sale_line_id": match.id})
                unmatched -= match

    def action_view_pocs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_order_poc.sale_order_poc_action"
        )
        action["domain"] = [("order_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
