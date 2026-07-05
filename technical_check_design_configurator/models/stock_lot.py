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


class StockLot(models.Model):
    _inherit = "stock.lot"

    # Workflow stage (design_state) и sales-потвърждението живеят в
    # sale_design_configurator. Тук са САМО техническите преходи и UI.

    design_sale_line_count = fields.Integer(
        string="Linked SO Lines",
        compute="_compute_design_sale_line_count",
        help="Брой SO редове, залепени към този дизайн лот (design_lot_id).",
    )

    def _compute_design_sale_line_count(self):
        SOL = self.env["sale.order.line"].sudo()
        for lot in self:
            lot.design_sale_line_count = SOL.search_count(
                [("design_lot_id", "=", lot.id)]
            ) if lot.id else 0

    def action_create_sale_order_from_lot(self):
        """Създай нова поръчка на база лота — линията носи продукта на лота +
        залепен design_lot_id. Клиентът се попълва от потребителя във формата.
        Видим само когато няма залепена SO линия."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Create Sale Order",
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_order_line": [
                    (0, 0, {
                        "product_id": self.product_id.id,
                        "product_uom_qty": 1.0,
                        "design_lot_id": self.id,
                    })
                ],
            },
        }

    def action_design_technical_confirm(self):
        """Technical person confirms: release the lot to production."""
        self.filtered(lambda lot: lot.design_state == "sales_confirmed").write(
            {"design_state": "technical_confirmed"}
        )
        return True

    def action_design_reset_to_sales(self):
        """Reopen technical editing (back to the technical queue)."""
        self.write({"design_state": "sales_confirmed"})
        return True

    def action_open_design_technical(self):
        """Open the configurator in technical mode (for the tablet menu).

        Same generic OWL dialog as the full configurator, but the ``level``
        param tells it to show sales fields read-only, technical fields
        editable and production fields hidden (driven by param_levels).
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": self.id,
                "level": "technical",
            },
        }
