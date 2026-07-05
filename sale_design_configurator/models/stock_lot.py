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


DESIGN_STATE = [
    ("draft", "Draft"),
    ("sales_confirmed", "Sales Confirmed"),
    ("technical_confirmed", "Technical Confirmed"),
]


class StockLot(models.Model):
    _inherit = "stock.lot"

    # -- Design workflow stage (sales -> technical -> production) -------------
    design_state = fields.Selection(
        DESIGN_STATE,
        string="Design Stage",
        default="draft",
        copy=False,
        index=True,
        help="Workflow stage of the design lot. Sales fills the sales-level "
        "parameters and confirms (locking them); the technical person fills "
        "the technical-level parameters on a tablet and confirms, releasing "
        "the lot to production. Levels come from the definition's param_levels.",
    )

    # -- Workflow transitions ------------------------------------------------

    def action_design_sales_confirm(self):
        """Sales confirms: lock sales-level parameters, hand over to technical.

        Technical/production transitions live in their own level modules
        (technical_check_design_configurator / mrp_technical_configurator).
        """
        self.filtered(lambda lot: lot.design_state == "draft").write(
            {"design_state": "sales_confirmed"}
        )
        return True

    # -- Helpers -------------------------------------------------------------

    @api.model
    def generate_design_lot_name(self, product_id):
        """
        Called from DesignConfiguratorWidget._saveDesignLot() via ORM.
        Returns a unique lot name. Ако е инсталиран product_category_lot_sequence
        и категорията на продукта има линкната последователност — ползва нея;
        иначе стандартния `stock.lot.serial`; накрая product-based fallback.
        """
        product = self.env["product.product"].browse(product_id)
        sequence = self.env["ir.sequence"]
        # Soft-check: без твърда зависимост от product_category_lot_sequence.
        if hasattr(product, "_get_lot_sequence"):
            sequence = product._get_lot_sequence()
        name = (
            sequence._next()
            if sequence
            else self.env["ir.sequence"].next_by_code("stock.lot.serial")
        )
        if not name:
            name = (
                f"DL-{product.default_code or product.id}"
                f"-{fields.Datetime.now().strftime('%y%m%d%H%M')}"
            )
        return name

    def action_open_design_configurator(self):
        """
        Button action on stock.lot form view.
        Returns a client action that opens DesignConfiguratorDialog via OWL.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": self.id,
            },
        }
