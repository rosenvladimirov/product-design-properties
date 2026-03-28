# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # -- Design lot linked to this SO line -----------------------------------
    design_lot_id = fields.Many2one(
        "stock.lot",
        string="Design Lot",
        copy=False,
        help=(
            "The design lot carrying the customer-specific parameters "
            "for this line. Created via the Design Configurator."
        ),
    )

    # -- Computed: does the selected product have a design definition? --------
    has_design_definition = fields.Boolean(
        compute="_compute_has_design_definition",
        store=False,
    )
    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        compute="_compute_has_design_definition",
        store=False,
        string="Design Parameter Set",
    )

    # -- Summary shown on the SO line (read-only) ----------------------------
    design_params_summary = fields.Char(
        compute="_compute_design_params_summary",
        string="Design Parameters",
        store=False,
    )

    # -- Computed fields -----------------------------------------------------

    @api.depends("product_id")
    def _compute_has_design_definition(self):
        """
        Check whether the selected product's BoM has a design parameter
        definition. Only the first active BoM is checked.
        """
        for line in self:
            if not line.product_id:
                line.has_design_definition = False
                line.design_param_definition_id = False
                continue
            bom = self.env["mrp.bom"].search(
                [
                    (
                        "product_tmpl_id",
                        "=",
                        line.product_id.product_tmpl_id.id,
                    ),
                    ("design_param_definition_id", "!=", False),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if bom:
                line.has_design_definition = True
                line.design_param_definition_id = (
                    bom.design_param_definition_id
                )
            else:
                line.has_design_definition = False
                line.design_param_definition_id = False

    @api.depends("design_lot_id", "design_lot_id.design_params")
    def _compute_design_params_summary(self):
        for line in self:
            lot = line.design_lot_id
            if not lot or not lot.design_params:
                line.design_params_summary = ""
                continue
            parts = []
            for k, v in (lot.design_params or {}).items():
                if v not in (None, False, ""):
                    parts.append(f"{k}: {v}")
            line.design_params_summary = "  \u00b7  ".join(parts[:6])

    # -- Onchange: reset design lot when product changes ---------------------

    @api.onchange("product_id")
    def _onchange_product_id_reset_design_lot(self):
        """Clear the design lot when the product changes."""
        self.design_lot_id = False

    # -- Action: open configurator dialog ------------------------------------

    def action_open_design_configurator(self):
        """
        Called from the 'Configure' button on the SO line.
        Returns a client action that opens DesignConfiguratorDialog.
        On lot creation, the lot is written back to this line via
        the JS callback -> Python RPC.
        """
        self.ensure_one()
        if not self.has_design_definition:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design definition"),
                    "message": _(
                        "The product '%s' has no BoM with a design "
                        "parameter definition."
                    )
                    % self.product_id.display_name,
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": (
                    self.design_lot_id.id if self.design_lot_id else False
                ),
                # Pass the SO line so the JS callback can write back
                "solId": self.id,
            },
        }

    def set_design_lot(self, lot_id):
        """
        RPC target called by the JS configurator after lot creation.
        Writes design_lot_id on this line.
        """
        self.ensure_one()
        self.design_lot_id = lot_id
        return True

    @api.model
    def get_design_definition_for_product(self, product_id):
        """
        Lightweight RPC called by the OWL SaleOrderLineProductField patch
        immediately after product selection.

        Returns::

            {"definitionId": int, "definitionCode": str}  if found
            False                                          if not found

        Only the first active BoM with a design_param_definition_id is used.
        """
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return False

        bom = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
                ("design_param_definition_id", "!=", False),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not bom:
            return False

        return {
            "definitionId": bom.design_param_definition_id.id,
            "definitionCode": bom.design_param_definition_id.code,
        }

    # -- Propagation to MO: pass design lot through procurement --------------

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id=group_id)
        if self.design_lot_id:
            vals["design_lot_id"] = self.design_lot_id.id
        return vals
