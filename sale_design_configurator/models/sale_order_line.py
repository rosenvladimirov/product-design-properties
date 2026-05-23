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
        Find design definition for the product. Search order:
        1. product.product.design_param_definition_id (direct on product)
        2. mrp.bom.design_param_definition_id (from BoM)
        Filtered by company active definitions if configured.
        """
        for line in self:
            if not line.product_id:
                line.has_design_definition = False
                line.design_param_definition_id = False
                continue

            active_defs = self.env.company.design_definition_ids
            found = False

            # 1. Check product.product directly
            prod_def = line.product_id.design_param_definition_id
            if prod_def:
                if not active_defs or prod_def in active_defs:
                    line.has_design_definition = True
                    line.design_param_definition_id = prod_def
                    found = True

            # 2. Fallback: check BoM
            if not found:
                domain = [
                    ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                    ("design_param_definition_id", "!=", False),
                    ("active", "=", True),
                ]
                if active_defs:
                    domain.append(("design_param_definition_id", "in", active_defs.ids))
                bom = self.env["mrp.bom"].search(domain, limit=1)
                if bom:
                    line.has_design_definition = True
                    line.design_param_definition_id = bom.design_param_definition_id
                    found = True

            if not found:
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
        Writes design_lot_id on this line and regenerates the user-facing
        line.name from the lot's design_params so quote/invoice docs reflect
        the latest configuration (the description is otherwise frozen at the
        value Odoo set when the product was first picked, usually just the
        product display name).
        """
        self.ensure_one()
        self.design_lot_id = lot_id
        try:
            self._regenerate_design_description()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to regenerate design description for line %s", self.id,
            )
        return True

    def _regenerate_design_description(self):
        """Rebuild ``line.name`` as the product display name + a bullet list
        of the lot's design_params.  Hidden from the description:

        - empty / False values
        - sub-property sentinels equal to ``use_main`` (UI placeholder for
          "inherit from main_X" — see ``_resolve_use_main_sentinels`` on the
          configurator widget)
        - color_X rows that resolve to the same value as ``main_color``
          (avoids 13 identical lines in the common case where every
          component inherits the main shutter color)

        Subclasses may override to inject extra rendering (per-shutter dims,
        custom labels, etc.); call ``super()`` to keep the bullet base.
        """
        for line in self:
            if not line.design_lot_id or not line.product_id:
                continue
            lot = line.design_lot_id
            rich = lot.read(["design_params"])[0].get("design_params") or []
            main_color_val = None
            for prop in rich:
                if isinstance(prop, dict) and prop.get("name") == "main_color":
                    main_color_val = prop.get("value")
                    break
            parts = [line.product_id.display_name]
            for prop in rich:
                if not isinstance(prop, dict):
                    continue
                value = prop.get("value")
                if value in (None, False, "", "use_main"):
                    continue
                name = prop.get("name") or ""
                label = prop.get("string") or name
                if not label:
                    continue
                if name.startswith("color_") and main_color_val and value == main_color_val:
                    continue
                if prop.get("type") == "selection":
                    sel = dict(prop.get("selection") or [])
                    value = sel.get(value, value)
                parts.append(f"• {label}: {value}")
            line.name = "\n".join(parts)

    @api.model
    def get_design_definition_for_product(self, product_id):
        """
        Lightweight RPC called by the OWL SaleOrderLineProductField patch
        immediately after product selection.

        Search order:
        1. product.product.design_param_definition_id (direct on product)
        2. mrp.bom.design_param_definition_id (from BoM)

        Returns::

            {"definitionId": int, "definitionCode": str}  if found
            False                                          if not found
        """
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return False

        active_defs = self.env.company.design_definition_ids

        # 1. Check product directly
        prod_def = product.design_param_definition_id
        if prod_def and (not active_defs or prod_def in active_defs):
            return {
                "definitionId": prod_def.id,
                "definitionCode": prod_def.code,
            }

        # 2. Fallback: check BoM
        domain = [
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ("design_param_definition_id", "!=", False),
            ("active", "=", True),
        ]
        if active_defs:
            domain.append(("design_param_definition_id", "in", active_defs.ids))
        bom = self.env["mrp.bom"].search(domain, limit=1)
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
