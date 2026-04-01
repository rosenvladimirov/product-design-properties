# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_open_design_configurator(self):
        """Preview the design configurator dialog for this product."""
        self.ensure_one()
        if not self.design_param_definition_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design definition"),
                    "message": _(
                        "Set a Design Definition on this product first."
                    ),
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": False,
            },
        }
