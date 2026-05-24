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

    def _build_design_param_bullets(self):
        """Return ``["label: value", ...]`` \u0437\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0438\u0442\u0435 design_params \u043d\u0430 lot-\u0430.

        \u0415\u0434\u0438\u043d source-of-truth \u0437\u0430 \u0432\u0441\u0438\u0447\u043a\u0438 render call site-\u043e\u0432\u0435:
        - ``_compute_design_params_summary`` (\u043a\u043e\u043c\u043f\u0430\u043a\u0442\u0435\u043d `\u00b7`-\u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d summary)
        - ``_get_sale_order_line_multiline_description_sale`` (PDF/invoice bullets)
        - ``_regenerate_design_description`` (line.name rebuild)

        Hide rules (\u043e\u0442 PR #1):
        - empty / False / "" / ``"use_main"`` sentinel (UI placeholder \u0437\u0430
          "inherit from main_X" \u2014 \u0440\u0435\u0437\u043e\u043b\u0432\u0430 \u0441\u0435 \u0432 JS \u043f\u0440\u0435\u0434\u0438 save, \u043d\u043e fallback \u0437\u0430
          legacy lot-\u043e\u0432\u0435)
        - ``color_X`` rows \u043a\u044a\u0434\u0435\u0442\u043e \u0441\u0442\u043e\u0439\u043d\u043e\u0441\u0442\u0442\u0430 \u0441\u044a\u0432\u043f\u0430\u0434\u0430 \u0441 ``main_color`` (\u0438\u0437\u0431\u044f\u0433\u0432\u0430
          13 \u0438\u0434\u0435\u043d\u0442\u0438\u0447\u043d\u0438 bullets \u0437\u0430 shutter color cascade)

        Resolution (\u043e\u0442 host's hot-fix 4-5 \u043c\u0430\u0439):
        - \u0427\u0435\u0442\u0435 \u043f\u0440\u0435\u0437 ``lot.read(["design_params"])`` \u0437\u0430 \u0434\u0430 merge-\u043d\u0435 properties
          framework metadata (string label, type, selection mapping)
        - Selection \u0441\u0442\u043e\u0439\u043d\u043e\u0441\u0442\u0438 \u2192 human label (``"standard"`` \u2192 ``"Standard"``)
          \u0432\u043c\u0435\u0441\u0442\u043e \u043c\u0430\u0448\u0438\u043d\u043d\u0438 \u043a\u043e\u0434\u043e\u0432\u0435
        """
        self.ensure_one()
        if not self.design_lot_id:
            return []
        rich = self.design_lot_id.read(["design_params"])[0].get("design_params") or []
        main_color_val = None
        for prop in rich:
            if isinstance(prop, dict) and prop.get("name") == "main_color":
                main_color_val = prop.get("value")
                break
        bullets = []
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
                for code, human in prop.get("selection") or []:
                    if code == value:
                        value = human
                        break
            bullets.append(f"{label}: {value}")
        return bullets

    @api.depends("design_lot_id", "design_lot_id.design_params")
    def _compute_design_params_summary(self):
        for line in self:
            bullets = line._build_design_param_bullets() if line.design_lot_id else []
            line.design_params_summary = "  \u00b7  ".join(bullets[:8])

    def _get_sale_order_line_multiline_description_sale(self):
        """Append bullet list \u043f\u043e\u0434 product display name \u0432 quote/invoice PDF-\u0438\u0442\u0435.

        super-pattern (host hot-fix) \u2014 \u0437\u0430\u043f\u0430\u0437\u0432\u0430 extras \u043e\u0442 \u0434\u0440\u0443\u0433\u0438 \u043c\u043e\u0434\u0443\u043b\u0438.
        Reuse-\u0432\u0430 ``_build_design_param_bullets`` \u0437\u0430 UUID\u2192label resolution.
        """
        desc = super()._get_sale_order_line_multiline_description_sale()
        if self.design_lot_id:
            bullets = self._build_design_param_bullets()
            if bullets:
                formatted = "\n".join(f"\u2022 {b}" for b in bullets)
                desc = f"{desc}\n{formatted}"
        return desc

    def write(self, vals):
        """Refresh ``line.name`` \u043a\u043e\u0433\u0430\u0442\u043e design_lot_id \u0441\u0435 \u0441\u043c\u0435\u043d\u044f \u043f\u0440\u0435\u0437 ORM
        (host's trigger \u2014 covers automation flows, \u043d\u0435 \u0441\u0430\u043c\u043e configurator)."""
        res = super().write(vals)
        if "design_lot_id" in vals:
            for line in self:
                if line.design_lot_id and line.product_id:
                    line._regenerate_design_description()
        return res

    @api.onchange("design_lot_id")
    def _onchange_design_lot_refresh_name(self):
        """Live UI refresh \u043d\u0430 ``line.name`` \u043f\u0440\u0438 \u0441\u043c\u044f\u043d\u0430 \u043d\u0430 design_lot_id."""
        for line in self:
            if line.design_lot_id and line.product_id:
                line._regenerate_design_description()

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
        """Rebuild ``line.name`` като product display name + bullet list от
        lot's design_params. Render логиката е в ``_build_design_param_bullets``
        (споделена с _get_sale_order_line_multiline_description_sale и
        _compute_design_params_summary за consistency).

        Subclasses могат да override-нат за extra rendering — call ``super()``
        за да запазите bullet base.
        """
        for line in self:
            if not line.design_lot_id or not line.product_id:
                continue
            bullets = line._build_design_param_bullets()
            parts = [line.product_id.display_name]
            parts.extend(f"• {b}" for b in bullets)
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
