# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # -- Receive design lot from SO procurement values -----------------------

    @api.model_create_multi
    def create(self, vals_list):
        """
        When an MO is created from a SO that has a design_lot_id on the
        line, the procurement passes it in the origin group values.
        We pick it up and set lot_producing_id automatically.
        """
        recs = super().create(vals_list)
        for production, vals in zip(recs, vals_list):
            design_lot_id = vals.get("design_lot_id")
            if design_lot_id and not production.lot_producing_id:
                production.lot_producing_id = design_lot_id
        return recs

    def action_open_design_configurator(self):
        """
        Button action on mrp.production form view.
        Opens the configurator to create/edit the lot_producing_id.
        On save the lot is linked to this MO.
        """
        self.ensure_one()
        bom = self.bom_id
        if not bom or not bom.design_param_definition_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design parameter set"),
                    "message": _(
                        "The BoM has no design parameter definition."
                    ),
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": bom.design_param_definition_id.id,
                "existingLotId": (
                    self.lot_producing_id.id
                    if self.lot_producing_id
                    else False
                ),
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
