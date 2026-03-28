# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    # -- Helpers -------------------------------------------------------------

    @api.model
    def generate_design_lot_name(self, product_id):
        """
        Called from DesignConfiguratorWidget._saveDesignLot() via ORM.
        Returns a unique lot name from sequence, or falls back to a
        product-based name.
        """
        name = self.env["ir.sequence"].next_by_code("stock.lot.serial")
        if not name:
            product = self.env["product.product"].browse(product_id)
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
