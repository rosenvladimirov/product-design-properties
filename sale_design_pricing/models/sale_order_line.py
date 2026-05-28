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
            result = bom._evaluate_cost_with_params(
                params,
                order_partner=line.order_id.partner_id or None,
            )
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
            # Visual indent за recursed lines (phantom/semi-finished walk).
            depth = len(ln.get("path") or [])
            indent = "&nbsp;&nbsp;" * (depth * 2) if depth else ""
            # Source badge: vendor / standard / child_bom
            src = ln.get("price_source", "standard")
            badge = {"vendor": "🏷", "standard": "📦", "child_bom": "🔗"}.get(src, "")
            seller = ln.get("seller_name", "")
            seller_html = f"<small class='text-muted'> · {seller}</small>" if seller else ""
            rows.append(
                f"<tr><td>{indent}{badge} {ln['product_name']}{seller_html}</td>"
                f"<td class='text-end'>{ln['qty']:.4f}</td>"
                f"<td class='text-end'>{ln['unit_cost']:.4f}</td>"
                f"<td class='text-end'>{ln['subtotal']:.2f}</td></tr>"
            )
        for op in result["operations"]:
            depth = len(op.get("path") or [])
            indent = "&nbsp;&nbsp;" * (depth * 2) if depth else ""
            rows.append(
                f"<tr><td>{indent}<i>{op['name']}</i></td>"
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

    # Customer-specific UX hooks (line.name auto-refresh от design params,
    # per-shutter dims pretty print и т.н.) се override-ват в clientski
    # модули — виж teolino_mrp_design_recompute/models/sale_order_line.py
    # за Teolino-specific implementation.
