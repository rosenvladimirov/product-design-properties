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
import logging

from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
        # Суровият речник (както в 18.0), не Property с етикети.
        flat = lot._get_stored_properties()
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
        """HTML разбивка на себестойността (материали + операции + надценки).

        В 19.0 имената идват през ``Markup.format`` (екранират се), а
        етикетите са преводими; числата и редът на колоните са като в 18.0.
        """
        _ = self.env._
        rows = Markup()
        for ln in result["lines"]:
            rows += Markup(
                "<tr><td>{}</td><td class='text-end'>{}</td>"
                "<td class='text-end'>{}</td><td class='text-end'>{}</td></tr>"
            ).format(
                ln["product_name"], f"{ln['qty']:.4f}",
                f"{ln['unit_cost']:.4f}", f"{ln['subtotal']:.2f}",
            )
        for op in result["operations"]:
            rows += Markup(
                "<tr><td><i>{}</i></td><td class='text-end'>{}</td>"
                "<td class='text-end'>{}</td><td class='text-end'>{}</td></tr>"
            ).format(
                op["name"],
                _("%(minutes)s min", minutes=f"{op['minutes']:.1f}"),
                _("%(rate)s/h", rate=f"{op['rate_per_hour']:.2f}"),
                f"{op['subtotal']:.2f}",
            )
        material_total = result["material_cost"] * (1.0 + mat_markup)
        labor_total = result["labor_cost"] * (1.0 + lab_markup)
        total = material_total + labor_total
        return Markup(
            "<table class='table table-sm'>"
            "<thead><tr><th>{item}</th><th class='text-end'>{qty}</th>"
            "<th class='text-end'>{unit}</th><th class='text-end'>{subtotal}</th></tr></thead>"
            "<tbody>{rows}</tbody>"
            "<tfoot>"
            "<tr><td colspan='3'><b>{l_mat}</b></td><td class='text-end'>{mat}</td></tr>"
            "<tr><td colspan='3'>{l_mat_markup}</td><td class='text-end'>{mat_total}</td></tr>"
            "<tr><td colspan='3'><b>{l_lab}</b></td><td class='text-end'>{lab}</td></tr>"
            "<tr><td colspan='3'>{l_lab_markup}</td><td class='text-end'>{lab_total}</td></tr>"
            "<tr><td colspan='3'><b>{l_total}</b></td><td class='text-end'><b>{total}</b></td></tr>"
            "</tfoot></table>"
        ).format(
            item=_("Item"), qty=_("Qty"), unit=_("Unit"), subtotal=_("Subtotal"),
            rows=rows,
            l_mat=_("Material cost"), mat=f"{result['material_cost']:.2f}",
            l_mat_markup=_("+ %(percent)s%% markup", percent=f"{mat_markup * 100:.0f}"),
            mat_total=f"{material_total:.2f}",
            l_lab=_("Labor cost"), lab=f"{result['labor_cost']:.2f}",
            l_lab_markup=_("+ %(percent)s%% markup", percent=f"{lab_markup * 100:.0f}"),
            lab_total=f"{labor_total:.2f}",
            l_total=_("List price"), total=f"{total:.2f}",
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
            # Описанието никога не бива да спира записа на партидата.
            _logger.exception(
                "Failed to refresh design description on line %s", self.id,
            )
        return res

    def _teolino_refresh_design_description(self):
        """Описанието на реда = името на продукта + списък с параметрите.

        Вика се от ``set_design_lot`` (изричното действие на конфигуратора),
        затова — както в 18.0 — пише и на потвърдена поръчка; системното
        връзване през ``write`` минава през ``_regenerate_design_description``
        на sale_design_configurator, което пипа само чернова/изпратена оферта.

        Списъкът идва от ``_build_design_param_bullets`` (скрива ``use_main``
        и цветовете, равни на основния, показва етикета на избора). Когато
        партидата носи размери по щора (``teolino_per_shutter_dims``, sc>1),
        плоските Width/Height/Thickness се заменят с един ред по панел:
        „• Dimensions: Sh.1 1000×2000, Sh.2 800×2500“ (преводимо).
        Hook за наследници (напр. teolino_fenestration).
        """
        _ = self.env._
        flat_dim_labels = ("Width (mm)", "Height (mm)", "Thickness (mm)")
        for line in self:
            if not line.design_lot_id or not line.product_id:
                continue
            lot = line.design_lot_id
            per_pairs = []
            if hasattr(lot, "teolino_get_per_shutter_pairs"):
                per_pairs = lot.teolino_get_per_shutter_pairs()
            parts = [line.product_id.display_name]
            if per_pairs:
                pretty = ", ".join(
                    _("Sh.%(index)s %(length)s×%(height)s",
                      index=i + 1, length=int(L), height=int(H))
                    for i, (L, H) in enumerate(per_pairs)
                )
                parts.append("• " + _("Dimensions: %(pairs)s", pairs=pretty))
            for bullet in line._build_design_param_bullets():
                label = bullet.split(": ", 1)[0]
                if per_pairs and label in flat_dim_labels:
                    continue
                parts.append(f"• {bullet}")
            line.name = "\n".join(parts)
