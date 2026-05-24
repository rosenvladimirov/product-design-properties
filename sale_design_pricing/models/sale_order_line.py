from markupsafe import Markup

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cost_material = fields.Float(
        compute="_compute_design_pricing", store=False, digits="Product Price",
    )
    cost_labor = fields.Float(
        compute="_compute_design_pricing", store=False, digits="Product Price",
    )
    list_price_material = fields.Float(
        compute="_compute_design_pricing", store=False, digits="Product Price",
    )
    list_price_labor = fields.Float(
        compute="_compute_design_pricing", store=False, digits="Product Price",
    )
    list_price_total = fields.Float(
        compute="_compute_design_pricing", store=False, digits="Product Price",
    )
    cost_breakdown_html = fields.Html(
        compute="_compute_design_pricing", store=False, sanitize=False,
    )

    @api.depends(
        "design_lot_id",
        "design_lot_id.design_params",
        "product_id",
        "product_id.product_tmpl_id.effective_material_markup_percent",
        "product_id.product_tmpl_id.effective_labor_markup_percent",
    )
    def _compute_design_pricing(self):
        for line in self:
            if not line.design_lot_id or not line.product_id:
                line.cost_material = 0.0
                line.cost_labor = 0.0
                line.list_price_material = 0.0
                line.list_price_labor = 0.0
                line.list_price_total = 0.0
                line.cost_breakdown_html = False
                continue

            tmpl = line.product_id.product_tmpl_id
            bom = self.env["mrp.bom"]._bom_find(
                products=line.product_id, company_id=line.company_id.id,
            ).get(line.product_id) or self.env["mrp.bom"]
            if not bom:
                line.cost_material = 0.0
                line.cost_labor = 0.0
                line.list_price_material = 0.0
                line.list_price_labor = 0.0
                line.list_price_total = 0.0
                line.cost_breakdown_html = False
                continue

            params = line._build_param_namespace()
            result = bom._evaluate_cost_with_params(params)
            mat_markup = (tmpl.effective_material_markup_percent or 0.0) / 100.0
            lab_markup = (tmpl.effective_labor_markup_percent or 0.0) / 100.0

            line.cost_material = result["material_cost"]
            line.cost_labor = result["labor_cost"]
            line.list_price_material = result["material_cost"] * (1.0 + mat_markup)
            line.list_price_labor = result["labor_cost"] * (1.0 + lab_markup)
            line.list_price_total = line.list_price_material + line.list_price_labor
            line.cost_breakdown_html = line._render_breakdown_html(result, mat_markup, lab_markup)

    def _build_param_namespace(self):
        """Flatten the lot's design_params (and template properties) into a name→value dict.

        Property fields store {name: value} where ``name`` is a hashed UUID. The user-facing
        label lives in the rich definition. We pass BOTH the hashed name (in case formulas
        reference it directly) and the human label (lower-cased, snake) for convenience.
        """
        self.ensure_one()
        ns = {}
        lot = self.design_lot_id
        if not lot:
            return ns
        rich = lot.read(["design_params"])[0].get("design_params") or []
        flat = dict(lot.design_params or {})
        for prop in rich:
            if not isinstance(prop, dict):
                continue
            name = prop.get("name")
            value = prop.get("value", flat.get(name))
            label = (prop.get("string") or "").strip()
            if name:
                ns[name] = value
            if label:
                ns[label] = value
                ns[label.lower().replace(" ", "_").replace("(", "").replace(")", "")] = value
        return ns

    def _render_breakdown_html(self, result, mat_markup, lab_markup):
        rows = []
        for ln in result["lines"]:
            rows.append(
                f"<tr><td>{ln['product_name']}</td>"
                f"<td class='text-end'>{ln['qty']:.4f}</td>"
                f"<td class='text-end'>{ln['unit_cost']:.4f}</td>"
                f"<td class='text-end'>{ln['subtotal']:.2f}</td></tr>"
            )
        for op in result["operations"]:
            rows.append(
                f"<tr><td><i>{op['name']}</i></td>"
                f"<td class='text-end'>{op['minutes']:.1f} min</td>"
                f"<td class='text-end'>{op['rate_per_hour']:.2f}/h</td>"
                f"<td class='text-end'>{op['subtotal']:.2f}</td></tr>"
            )
        body = "".join(rows)
        material_total = result["material_cost"] * (1.0 + mat_markup)
        labor_total = result["labor_cost"] * (1.0 + lab_markup)
        total = material_total + labor_total
        return Markup(
            "<table class='table table-sm'>"
            "<thead><tr><th>Item</th><th class='text-end'>Qty</th>"
            "<th class='text-end'>Unit</th><th class='text-end'>Subtotal</th></tr></thead>"
            f"<tbody>{body}</tbody>"
            "<tfoot>"
            f"<tr><td colspan='3'><b>Material cost</b></td><td class='text-end'>{result['material_cost']:.2f}</td></tr>"
            f"<tr><td colspan='3'>+ {mat_markup * 100:.0f}% markup</td><td class='text-end'>{material_total:.2f}</td></tr>"
            f"<tr><td colspan='3'><b>Labor cost</b></td><td class='text-end'>{result['labor_cost']:.2f}</td></tr>"
            f"<tr><td colspan='3'>+ {lab_markup * 100:.0f}% markup</td><td class='text-end'>{labor_total:.2f}</td></tr>"
            f"<tr><td colspan='3'><b>List price</b></td><td class='text-end'><b>{total:.2f}</b></td></tr>"
            "</tfoot></table>"
        )

    def _get_display_price(self):
        self.ensure_one()
        if self.design_lot_id and self.has_design_definition and self.list_price_total:
            return self.list_price_total
        return super()._get_display_price()

    @api.depends("design_lot_id", "design_lot_id.design_params")
    def _compute_price_unit(self):
        return super()._compute_price_unit()

    # ── Auto-regenerate line.name after every design lot save ─────────────
    # User-facing description on the SO line must reflect the LATEST lot
    # params so customer-facing docs (quote/invoice) are correct.  Without
    # this hook, line.name stays frozen at whatever was set when the line
    # was first created (usually just the product name).

    def set_design_lot(self, lot_id):
        res = super().set_design_lot(lot_id)
        try:
            self._teolino_refresh_design_description()
        except Exception:
            # Never break lot save because of description rendering
            import logging
            logging.getLogger(__name__).exception(
                "Failed to refresh design description on line %s", self.id,
            )
        return res

    def _teolino_refresh_design_description(self):
        """Rebuild line.name from product display name + bullet list of
        current lot design_params.  Skips use_main sentinels and color_X
        rows that match main_color.  When teolino_per_shutter_dims is set
        (sc>1), replaces the single Width/Height rows with a per-panel
        line: '• Размери: Щ.1 1000×2000, Щ.2 800×2500'."""
        for line in self:
            if not line.design_lot_id or not line.product_id:
                continue
            lot = line.design_lot_id
            rich = lot.read(["design_params"])[0].get("design_params") or []
            # First pass: index by name + grab main_color resolved value
            main_color_val = None
            for prop in rich:
                if isinstance(prop, dict) and prop.get("name") == "main_color":
                    main_color_val = prop.get("value")
                    break
            # Per-shutter pairs (replaces flat Width/Height when present)
            per_pairs = []
            if hasattr(lot, "teolino_get_per_shutter_pairs"):
                per_pairs = lot.teolino_get_per_shutter_pairs()
            skip_flat_dims = bool(per_pairs)
            parts = [line.product_id.display_name]
            if skip_flat_dims:
                pretty = ", ".join(
                    f"Щ.{i+1} {int(L)}×{int(H)}" for i, (L, H) in enumerate(per_pairs)
                )
                parts.append(f"• Размери: {pretty}")
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
                # Skip per-component color rows that match main_color —
                # they're redundant noise on the quote/invoice.
                if name.startswith("color_") and main_color_val and value == main_color_val:
                    continue
                # Skip flat Width/Height when we already rendered per-shutter dims.
                if skip_flat_dims and label in ("Width (mm)", "Height (mm)", "Thickness (mm)"):
                    continue
                # Selection: prefer human label over raw value
                if prop.get("type") == "selection":
                    sel = dict(prop.get("selection") or [])
                    value = sel.get(value, value)
                parts.append(f"• {label}: {value}")
            line.name = "\n".join(parts)
