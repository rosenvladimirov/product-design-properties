# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
from odoo import _, fields, models
from odoo.exceptions import UserError


class DesignLotCreateWizard(models.TransientModel):
    _name = "design.lot.create.wizard"
    _description = "Create Design Lot (select product)"

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        help="Product to design — same selection as a sale order line.",
    )

    def action_open_configurator(self):
        """Намира дизайн дефиницията на продукта (както в SO реда) и отваря
        конфигуратора (ниво sales, с 3D). Лотът се създава при запис в
        конфигуратора (без съществуващ лот → create)."""
        self.ensure_one()
        defn = self.env["sale.order.line"].get_design_definition_for_product(
            self.product_id.id
        )
        if not defn:
            raise UserError(
                _("Product '%s' has no design parameter definition "
                  "(neither on the product nor on its BoM).")
                % self.product_id.display_name
            )
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": defn["definitionId"],
                "existingLotId": False,
                "level": "sales",
            },
        }
