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
from odoo import _, api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    design_lot_id = fields.Many2one(
        "stock.lot",
        string="Design Lot",
        help=(
            "Design lot propagated from the originating sale order line. "
            "Carries design context through MTO procurement chains "
            "(SO → delivery move → component move → MO)."
        ),
    )

    def _prepare_procurement_values(self):
        """Forward design_lot_id to upstream MTO procurements so manufacture
        and purchase rules see it in their _prepare_mo_vals / _get_stock_move_values.
        """
        vals = super()._prepare_procurement_values()
        if self.design_lot_id:
            vals["design_lot_id"] = self.design_lot_id.id
        return vals


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    design_lot_id = fields.Many2one(
        "stock.lot",
        string="Design Lot",
        help="Transient inlet from SO procurement; copied into lot_producing_id on create.",
    )

    # -- Receive design lot from SO procurement values -----------------------

    @api.model_create_multi
    def create(self, vals_list):
        """
        When an MO is created from a SO that has a design_lot_id on the
        line, the procurement passes it in the origin group values.
        We pick it up and set lot_producing_id automatically.
        """
        recs = super().create(vals_list)
        for production, vals in zip(recs, vals_list, strict=False):
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
                    "message": _("The BoM has no design parameter definition."),
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
                    self.lot_producing_id.id if self.lot_producing_id else False
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

    def _prepare_mo_vals(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
        bom,
    ):
        mo_vals = super()._prepare_mo_vals(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
            bom,
        )
        if values.get("design_lot_id"):
            mo_vals["design_lot_id"] = values["design_lot_id"]
        return mo_vals
