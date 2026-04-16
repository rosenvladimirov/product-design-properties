# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # -- Receive design lot from SO procurement values -----------------------

    @api.model_create_multi
    def create(self, vals_list):
        """
        When an MO is created from a SO that has a design_lot_id on the
        line, the procurement passes it in the origin group values.
        We pick it up and add it to lot_producing_ids automatically.
        """
        recs = super().create(vals_list)
        for production, vals in zip(recs, vals_list, strict=False):
            design_lot_id = vals.get("design_lot_id")
            if design_lot_id and not production.lot_producing_ids:
                production.lot_producing_ids = [(4, design_lot_id)]
        return recs

    def action_open_design_configurator(self):
        """
        Button action on mrp.production form view.
        Opens the configurator to create/edit the design lot (first lot
        in ``lot_producing_ids``). On save the lot is linked to this MO.
        """
        self.ensure_one()
        bom = self.bom_id
        if not bom or not bom.design_param_definition_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design parameter set"),
                    "message": _("The BoM has no design parameter definition."),
                    "type": "warning",
                },
            }
        existing = self.lot_producing_ids[:1]
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": bom.design_param_definition_id.id,
                "existingLotId": existing.id if existing else False,
                "moId": self.id,
            },
        }


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_stock_move_values(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
    ):
        move_vals = super()._get_stock_move_values(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
        )
        # Pass design_lot_id into the manufacturing order via the
        # group_id procurement values -> MO create vals
        if values.get("design_lot_id"):
            move_vals["design_lot_id"] = values["design_lot_id"]
        return move_vals
