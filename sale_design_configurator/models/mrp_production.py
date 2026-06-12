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
            "Used to carry design parameters through MTO procurement from "
            "SO → MO and SO → PO."
        ),
    )

    def _prepare_procurement_values(self):
        """Propagate design_lot_id to upstream MTO procurements, so the
        manufacture / purchase rule sees it in ``_prepare_mo_vals`` /
        ``_prepare_purchase_order_vals``.
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
        help="Transient design lot from SO procurement; copied into lot_producing_ids on create.",
    )

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
        # Pass design_lot_id from SO procurement into every downstream move
        # (delivery + component moves) so the design context travels through
        # MTO chains to MOs and (future) to POs.
        if values.get("design_lot_id"):
            move_vals["design_lot_id"] = values["design_lot_id"]
        return move_vals

    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_dest_id,
                        name, origin, company_id, values, bom):
        mo_vals = super()._prepare_mo_vals(product_id, product_qty, product_uom,
                                           location_dest_id, name, origin, company_id,
                                           values, bom)
        # Propagate design_lot_id from procurement values → MO create vals.
        # `MrpProduction.create()` copies vals['design_lot_id'] into lot_producing_ids.
        if values.get("design_lot_id"):
            mo_vals["design_lot_id"] = values["design_lot_id"]
        return mo_vals
