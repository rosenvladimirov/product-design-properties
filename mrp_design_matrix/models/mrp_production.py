# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from .zen_engine import ZenWrapper

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # ── Public entry point ────────────────────────────────────────────────

    def action_confirm(self):
        res = super().action_confirm()
        for production in self:
            if production.bom_id and production.bom_id.constraint_table:
                production._generate_design_matrix_moves()
        return res

    # ── Main algorithm ────────────────────────────────────────────────────

    def _generate_design_matrix_moves(self):
        """
        Execute the T0/T1/T2/T3 rule chain for this MO.

        Called from action_confirm() when the BoM has at least a
        constraint_table defined.

        Algorithm:
            1. Build design_context from lot_producing_id.
            2. T0: validate constraints (ERROR stops, WARNING logs).
            3. T1: compute geometry / forced values → full_context.
            4. BoM lines: qty_formula × matrix_coeff → move_raw.
            5. T2 ad-hoc: resolve product (direct / PTAV) → move_raw.
            6. T3: create workorders.
            7. Semi-finished: create child lots or find matching stock.
        """
        self.ensure_one()
        bom = self.bom_id
        lot = self.lot_producing_id

        if not lot:
            _logger.warning(
                "MO %s has no lot_producing_id — design matrix skipped.",
                self.name,
            )
            return

        # 1. Build context
        ctx = lot._get_design_context()
        ctx["qty"] = self.product_qty

        # 2. T0 — constraints
        if bom.constraint_table:
            t0 = ZenWrapper.evaluate(bom.constraint_table, ctx)
            for err in t0.get("errors", []):
                raise UserError(
                    _("Design constraint violation: %s") % err.get("message", err)
                )
            for warn in t0.get("warnings", []):
                self.message_post(
                    body=_("Design warning: %s") % warn.get("message", warn)
                )

        # 3. T1 — geometry + forced values
        full_ctx = dict(ctx)
        if bom.geometry_table:
            t1 = ZenWrapper.evaluate(bom.geometry_table, ctx)
            # forced values from T1 override user-supplied values
            full_ctx.update(t1)

        # 4. BoM lines × (formula_qty × coeff)  [T2 Type 1: O-variants]
        for line in bom.bom_line_ids:
            qty_base = self._eval_bom_line_formula(line, full_ctx)
            coeff = self._eval_matrix_coeff(line, full_ctx)
            qty_final = qty_base * coeff
            if qty_final > 0.0:
                self._create_or_update_matrix_move(
                    line.product_id, qty_final, line.product_uom_id, line
                )

        # 5. T2 ad-hoc rows  [Type 2: direct ref / Type 3: PTAV]
        if bom.material_table:
            t2 = ZenWrapper.evaluate(bom.material_table, full_ctx)
            for item in t2 if isinstance(t2, list) else t2.get("result", []):
                coeff = item.get("coefficient", 0.0)
                if coeff <= 0.0:
                    continue
                product = self._resolve_t2_product(item, full_ctx)
                if not product:
                    raise UserError(
                        _("Cannot resolve product for T2 item: %s") % item
                    )
                qty = self._eval_qty_expr(item.get("quantity", 0), full_ctx)
                uom = self.env.ref(item["uom_ref"]) if item.get("uom_ref") else product.uom_id
                self._create_or_update_matrix_move(product, qty * coeff, uom)

        # 6. T3 — workorders
        if bom.operation_table:
            t3 = ZenWrapper.evaluate(bom.operation_table, full_ctx)
            for op in t3 if isinstance(t3, list) else t3.get("result", []):
                self._create_matrix_workorder(op)

        # 7. Semi-finished: child lots / mto_stop
        self._handle_semifinished_lots(full_ctx)

    # ── Product resolution ────────────────────────────────────────────────

    def _resolve_t2_product(self, item: dict, ctx: dict):
        """Dispatch T2 output to the correct product resolution method."""
        # Type 2 — direct external ID
        if "product_ref" in item:
            return self.env.ref(item["product_ref"])

        # Type 3 — PTAV resolution
        if "product_tmpl_ref" in item and "param_attribute_map" in item:
            tmpl = self.env.ref(item["product_tmpl_ref"])
            return self._resolve_variant_by_ptav(
                tmpl, item["param_attribute_map"], ctx
            )
        return False

    def _resolve_variant_by_ptav(self, tmpl, param_attr_map: dict, design_ctx: dict):
        """
        Resolve a product.product variant via PTAV.

        :param tmpl:           product.template
        :param param_attr_map: {design_param_key: attribute_external_id}
        :param design_ctx:     flat design context dict
        :returns: product.product or False
        """
        PTAV = self.env["product.template.attribute.value"]
        needed = PTAV.browse()

        for param_key, attr_ref in param_attr_map.items():
            value = design_ctx.get(param_key)
            if value is None:
                continue
            try:
                attribute = self.env.ref(attr_ref)
            except ValueError:
                _logger.warning("Unknown attribute ref: %s", attr_ref)
                continue
            ptav = PTAV.search([
                ("product_tmpl_id", "=", tmpl.id),
                ("attribute_id",    "=", attribute.id),
                ("name",            "=", str(value)),
            ], limit=1)
            if ptav:
                needed |= ptav
            else:
                _logger.warning(
                    "No PTAV found for tmpl=%s attr=%s value=%s",
                    tmpl.display_name, attribute.name, value,
                )

        if not needed:
            return False
        return tmpl._get_variant_for_combination(needed)

    # ── Semi-finished chain ───────────────────────────────────────────────

    def _handle_semifinished_lots(self, full_ctx: dict):
        """Assign child lots to semi-finished move lines."""
        for move in self.move_raw_ids.filtered(
            lambda m: m.bom_line_id and m.bom_line_id.child_definition_id
        ):
            line = move.bom_line_id
            child_params = self._extract_child_params(line, full_ctx)

            if line.mto_stop:
                match = self.env["stock.lot"]._find_matching_stock_lot(
                    move.product_id, child_params
                )
                if match:
                    move.forced_lot_ids = [(4, match.id)]
                # else: procurement will handle the PO with child_params
            else:
                child_lot = self.env["stock.lot"]._create_child_lot(
                    self.lot_producing_id, line, move.product_id
                )
                move.forced_lot_ids = [(4, child_lot.id)]

    def _extract_child_params(self, bom_line, full_ctx: dict) -> dict:
        """Evaluate param_extraction_map against full_ctx."""
        result = {}
        for child_key, source in (bom_line.param_extraction_map or {}).items():
            if source in full_ctx:
                result[child_key] = full_ctx[source]
            else:
                try:
                    result[child_key] = safe_eval(source, full_ctx)
                except Exception:
                    result[child_key] = None
        return result

    # ── Helpers ───────────────────────────────────────────────────────────

    def _eval_bom_line_formula(self, line, ctx: dict) -> float:
        """
        Evaluate the quantity_formula of a BoM line against ctx.
        Falls back to product_qty if no formula is set.
        """
        if hasattr(line, "_eval_quantity_formula") and line.quantity_formula:
            return line._eval_quantity_formula(
                line.product_id,
                line.product_uom_id,
                self.product_qty,
                self,
            ) or 0.0
        return line.product_qty

    def _eval_matrix_coeff(self, line, ctx: dict) -> float:
        """
        Return the runtime coefficient for a BoM line.
        Falls back to coeff_default (1.0 by default).
        """
        if line.matrix_coeff_rule and self.bom_id.material_table:
            t2 = ZenWrapper.evaluate(self.bom_id.material_table, ctx)
            items = t2 if isinstance(t2, list) else t2.get("result", [])
            for item in items:
                if item.get("bom_line_coeff_key") == line.matrix_coeff_rule:
                    return float(item.get("coefficient", line.coeff_default))
        return line.coeff_default if hasattr(line, "coeff_default") else 1.0

    def _eval_qty_expr(self, expr, ctx: dict) -> float:
        """Evaluate a quantity expression — float literal or safe_eval str."""
        if isinstance(expr, (int, float)):
            return float(expr)
        try:
            return float(safe_eval(str(expr), ctx))
        except Exception:
            return 0.0

    def _create_or_update_matrix_move(self, product, qty, uom, bom_line=None):
        """Create a raw material move for the MO."""
        vals = {
            "name": product.display_name,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": uom.id,
            "raw_material_production_id": self.id,
            "location_id": self.location_src_id.id,
            "location_dest_id": product.with_company(
                self.company_id
            ).property_stock_production.id,
            "company_id": self.company_id.id,
        }
        if bom_line:
            vals["bom_line_id"] = bom_line.id
        self.env["stock.move"].create(vals)

    def _create_matrix_workorder(self, op: dict):
        """Create a workorder from a T3 output row."""
        workcenter_ref = op.get("workcenter_ref")
        if not workcenter_ref:
            return
        try:
            workcenter = self.env.ref(workcenter_ref)
        except ValueError:
            _logger.warning("Unknown workcenter ref: %s", workcenter_ref)
            return
        self.env["mrp.workorder"].create({
            "name": op.get("name", workcenter.name),
            "production_id": self.id,
            "workcenter_id": workcenter.id,
            "product_uom_id": self.product_uom_id.id,
            "qty_production": self.product_qty,
        })
