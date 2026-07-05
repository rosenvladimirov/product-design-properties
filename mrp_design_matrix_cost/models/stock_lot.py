# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
from odoo import models


class StockLot(models.Model):
    _inherit = "stock.lot"

    def get_design_cost(self):
        """Себестойност/продажна за дизайна на лота — извиква се от cost панела
        на конфигуратора (ниво cost). Само ЧЕТЕ."""
        self.ensure_one()
        # server-side gate — групата пазеше само UI-а, методът беше отворен по RPC
        self.env["mrp.bom"]._ensure_design_cost_access()
        product = self.product_id
        empty = {
            "lines": [], "operations": [],
            "total_material": 0.0, "total_labor": 0.0, "total_cost": 0.0,
            "sale_suggested": 0.0, "sale_actual": None, "currency_id": False,
        }
        if not product:
            return dict(empty, error="No product")
        bom = self.env["mrp.bom"].sudo()._bom_find(product).get(product)
        if not bom:
            return dict(empty, error="No BoM for product")
        ctx = self._get_design_context() if hasattr(self, "_get_design_context") else {}
        # Реалната продажна се чете от SO реда (price_unit = резултат на
        # ценоразписа в core). Ако лотът не е на поръчка → няма реална цена.
        so_line = self.env["sale.order.line"].sudo().search(
            [("design_lot_id", "=", self.id)], limit=1
        )
        return bom.simulate_design_cost(ctx, 1.0, sale_record=so_line or None)

    def action_open_design_cost(self):
        """Отваря конфигуратора на ниво cost (cost панелът на мястото на 3D)."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": self.id,
                "level": "cost",
            },
        }
