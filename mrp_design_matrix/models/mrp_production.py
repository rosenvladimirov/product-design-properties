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

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper

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
            4. T2: evaluate once, reuse for O-variant coeff lookup
               and ad-hoc rows (avoids N+1 on bom_line_ids).
            5. BoM lines: qty_formula × matrix_coeff → move_raw.
            6. T2 ad-hoc: resolve product (direct / PTAV) → move_raw.
            7. T3: create workorders.
            8. Semi-finished: create child lots or find matching stock.

        Performance notes:
            - T2 material_table is evaluated ONCE per MO, not per BoM
              line.  Before this optimisation a 50-line BoM would call
              ``ZenWrapper.evaluate`` 51× with the same arguments.
            - Prefetches are batched on ``bom_line_ids`` before the
              loop so the ORM issues a single SELECT for the fields
              we access during move creation.
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

        # 1–2. Build context + T0 validation + T0 context flags
        ctx = lot._get_design_context()
        ctx["qty"] = self.product_qty
        t0_ctx = self._eval_t0_constraints(bom, ctx)
        ctx.update(t0_ctx)

        # 3. T1 — geometry + forced values
        full_ctx = self._eval_t1_geometry(bom, ctx)

        # 4. T2 — evaluate once, split into (all rows, coeff-by-key map)
        t2_rows, t2_coeff_by_key = self._eval_t2_materials(bom, full_ctx)

        # 5. BoM line moves (with prefetch) + 6. T2 ad-hoc moves
        self._generate_bom_line_moves(bom, full_ctx, t2_coeff_by_key)
        self._generate_t2_adhoc_moves(t2_rows, full_ctx)

        # 7. T3 — workorders
        if bom.operation_table:
            t3 = ZenWrapper.evaluate(bom.operation_table, full_ctx)
            for op in t3 if isinstance(t3, list) else t3.get("result", []):
                self._create_matrix_workorder(op, full_ctx)

        # 8. Semi-finished: child lots / mto_stop
        self._handle_semifinished_lots(full_ctx)

    # ── Step helpers (split from main algorithm for complexity) ──────────

    def _eval_t0_constraints(self, bom, ctx: dict) -> dict:
        """Run T0 constraint_table; raise on errors, log warnings.

        Returns any non-reserved keys from the T0 result as context
        variables that downstream tables (T1/T2/T3) and BoM line
        formulas can use.  For example a T0 rule can set
        ``needs_reinforcement = true`` and a formula can react to it.
        """
        if not bom.constraint_table:
            return {}
        t0 = ZenWrapper.evaluate(bom.constraint_table, ctx)
        for err in t0.get("errors", []):
            raise UserError(
                _("Design constraint violation: %s") % err.get("message", err)
            )
        for warn in t0.get("warnings", []):
            self.message_post(body=_("Design warning: %s") % warn.get("message", warn))
        # Pass non-reserved keys as context additions for T1/T2/T3/formulas
        _reserved = {"errors", "warnings"}
        return {k: v for k, v in t0.items() if k not in _reserved}

    def _eval_t1_geometry(self, bom, ctx: dict) -> dict:
        """Run T1 geometry_table; return ``ctx`` merged with T1 outputs."""
        full_ctx = dict(ctx)
        if bom.geometry_table:
            t1 = ZenWrapper.evaluate(bom.geometry_table, ctx)
            # forced values from T1 override user-supplied values
            full_ctx.update(t1)
        return full_ctx

    def _eval_t2_materials(self, bom, full_ctx: dict) -> tuple:
        """
        Evaluate T2 ``material_table`` once.

        :returns: ``(rows, coeff_by_key)`` where ``rows`` is the full
                  list of output items and ``coeff_by_key`` maps each
                  ``bom_line_coeff_key`` to its coefficient (for O-variant
                  activation in the BoM-line loop).
        """
        if not bom.material_table:
            return [], {}
        raw = ZenWrapper.evaluate(bom.material_table, full_ctx)
        rows = raw if isinstance(raw, list) else raw.get("result", [])
        coeff_by_key = {}
        for item in rows:
            key = item.get("bom_line_coeff_key")
            if key:
                coeff_by_key[key] = float(item.get("coefficient", 0.0))
        return rows, coeff_by_key

    def _generate_bom_line_moves(
        self, bom, full_ctx: dict, t2_coeff_by_key: dict
    ) -> None:
        """Loop over bom_line_ids and create raw moves."""
        bom_lines = bom.bom_line_ids
        # Batch prefetch: turns N queries into one for large BoMs.
        bom_lines.fetch(
            [
                "product_id",
                "product_uom_id",
                "product_qty",
                "quantity_formula",
                "coeff_default",
                "matrix_coeff_rule",
            ]
        )
        for line in bom_lines:
            qty_base, move_product, move_uom, add_products = (
                self._unpack_formula_result(line, full_ctx)
            )
            coeff = self._eval_matrix_coeff_cached(line, t2_coeff_by_key)
            qty_final = qty_base * coeff
            if qty_final > 0.0:
                self._create_or_update_matrix_move(
                    move_product, qty_final, move_uom, line
                )
            # Extra products injected by the formula's add_products
            for extra in add_products:
                self._create_formula_extra_move(extra, full_ctx)

    def _unpack_formula_result(self, line, full_ctx: dict) -> tuple:
        """Evaluate the BoM line formula and return ``(qty, product, uom, add_products)``.

        ``add_products`` is a list of dicts that the formula can populate::

            add_products = [
                {"ref": "module.xml_id", "quantity": width * 0.002},
                {"product": env.ref("..."), "quantity": 5, "uom": env.ref("...")},
            ]
        """
        formula_result = self._eval_bom_line_formula(line, full_ctx)
        add_products = []
        if isinstance(formula_result, dict):
            qty_base = formula_result.get("quantity", 0) or 0.0
            move_product = formula_result.get("product") or line.product_id
            move_uom = formula_result.get("uom") or line.product_uom_id
            add_products = formula_result.get("add_products") or []
        else:
            qty_base = formula_result
            move_product = line.product_id
            move_uom = line.product_uom_id
        return qty_base, move_product, move_uom, add_products

    def _generate_t2_adhoc_moves(self, t2_rows: list, full_ctx: dict) -> None:
        """Create raw moves for ad-hoc T2 rows (direct ref / PTAV)."""
        for item in t2_rows:
            coeff = item.get("coefficient", 0.0)
            if coeff <= 0.0:
                continue
            # Skip rows already used as O-variant coefficients — those
            # generated a move in the BoM-line loop.
            if item.get("bom_line_coeff_key"):
                continue
            product = self._resolve_t2_product(item, full_ctx)
            if not product:
                raise UserError(_("Cannot resolve product for T2 item: %s") % item)
            qty = self._eval_qty_expr(item.get("quantity", 0), full_ctx)
            uom = (
                self.env.ref(item["uom_ref"]) if item.get("uom_ref") else product.uom_id
            )
            self._create_or_update_matrix_move(product, qty * coeff, uom)

    # ── Product resolution ────────────────────────────────────────────────

    def _resolve_t2_product(self, item: dict, ctx: dict):
        """Dispatch T2 output to the correct product resolution method."""
        # Type 2 — direct external ID
        if "product_ref" in item:
            return self.env.ref(item["product_ref"])

        # Type 3 — PTAV resolution
        if "product_tmpl_ref" in item and "param_attribute_map" in item:
            tmpl = self.env.ref(item["product_tmpl_ref"])
            return self._resolve_variant_by_ptav(tmpl, item["param_attribute_map"], ctx)
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
            ptav = PTAV.search(
                [
                    ("product_tmpl_id", "=", tmpl.id),
                    ("attribute_id", "=", attribute.id),
                    ("name", "=", str(value)),
                ],
                limit=1,
            )
            if ptav:
                needed |= ptav
            else:
                _logger.warning(
                    "No PTAV found for tmpl=%s attr=%s value=%s",
                    tmpl.display_name,
                    attribute.name,
                    value,
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

    def _eval_bom_line_formula(self, line, ctx: dict):
        """
        Evaluate the quantity_formula of a BoM line against ctx.

        Returns float (quantity) or dict {quantity, product, uom} when
        the formula overrides product/uom.  Falls back to product_qty
        if no formula is set.
        """
        if hasattr(line, "_eval_quantity_formula") and line.quantity_formula:
            result = line._eval_quantity_formula(
                line.product_id,
                line.product_uom_id,
                self.product_qty,
                self,
                design_context=ctx,
            )
            if result is None:
                return line.product_qty
            if isinstance(result, dict):
                return result
            return result or 0.0
        return line.product_qty

    def _eval_matrix_coeff_cached(self, line, t2_coeff_by_key: dict) -> float:
        """
        Look up a BoM line's matrix coefficient in a pre-evaluated
        ``{bom_line_coeff_key: coefficient}`` dict produced once by
        ``_generate_design_matrix_moves``.

        This replaces the per-line ``ZenWrapper.evaluate`` call that
        used to run inside the loop.  For a 50-line BoM the T2 table
        is now evaluated once instead of 50 times.
        """
        if line.matrix_coeff_rule and line.matrix_coeff_rule in t2_coeff_by_key:
            return t2_coeff_by_key[line.matrix_coeff_rule]
        return line.coeff_default if hasattr(line, "coeff_default") else 1.0

    def _eval_matrix_coeff(self, line, ctx: dict) -> float:
        """
        Return the runtime coefficient for a BoM line.
        Falls back to coeff_default (1.0 by default).

        .. deprecated::
            Kept for backward compatibility with external callers.  The
            main algorithm in ``_generate_design_matrix_moves`` now uses
            the cached variant ``_eval_matrix_coeff_cached`` to avoid
            re-evaluating the T2 table for every BoM line.
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
        if isinstance(expr, int | float):
            return float(expr)
        try:
            return float(safe_eval(str(expr), ctx))
        except Exception:
            return 0.0

    def _create_formula_extra_move(self, item: dict, ctx: dict):
        """Create a raw move for a product added via formula ``add_products``.

        Supported dict keys:
            - ``product``: product.product recordset (direct)
            - ``ref``: XML ID string, resolved via ``env.ref()``
            - ``quantity``: float or safe_eval expression
            - ``uom``: product.uom recordset (optional, defaults to product UoM)
        """
        product = item.get("product")
        if not product:
            ref = item.get("ref")
            if ref:
                product = self.env.ref(ref, raise_if_not_found=False)
        if not product:
            _logger.warning("add_products: skipping item without product: %s", item)
            return
        qty = self._eval_qty_expr(item.get("quantity", 0), ctx)
        if qty <= 0:
            return
        uom = item.get("uom") or product.uom_id
        self._create_or_update_matrix_move(product, qty, uom)

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

    def _create_matrix_workorder(self, op: dict, ctx=None):
        """Create a workorder from a T3 output row.

        ``duration_formula`` is the expected duration in minutes — either a
        number already evaluated by the zen engine, or an expression to
        evaluate against the matrix context ``ctx``.  The first matrix
        workorder also collects the still-unassigned raw moves so the
        materials are consumed at that operation.
        """
        # Толерантен reader за ДВЕТЕ T3 схеми (lockstep порт от 19.0):
        # - нова: ``workcenter_code`` → search по code (ZEN връща string literal
        #   с кавички → strip). САМО собствената фирма или споделен център —
        #   check_company на workcenter_id иначе събаря MO confirm.
        # - legacy: ``workcenter_ref`` (xmlid) → env.ref.
        workcenter = None
        code = op.get("workcenter_code")
        if isinstance(code, str):
            code = code.strip().strip('"').strip("'").strip()
        if code:
            WC = self.env["mrp.workcenter"].sudo()
            workcenter = WC.search(
                [("code", "=", code), ("company_id", "=", self.company_id.id)],
                limit=1,
            ) or WC.search(
                [("code", "=", code), ("company_id", "=", False)], limit=1
            )
            if not workcenter and WC.search([("code", "=", code)], limit=1):
                _logger.info(
                    "T3 op %r: workcenter exists only in another company — "
                    "skipped for MO %s (company %s).",
                    code, self.name, self.company_id.id)
                return
        if not workcenter:
            workcenter_ref = op.get("workcenter_ref")
            if not workcenter_ref:
                _logger.warning(
                    "T3 op row has no resolvable workcenter (code=%r, ref=%r) "
                    "— skipped.", op.get("workcenter_code"),
                    op.get("workcenter_ref"))
                return
            try:
                workcenter = self.env.ref(workcenter_ref)
            except ValueError:
                _logger.warning("Unknown workcenter ref: %s", workcenter_ref)
                return
        duration = self._eval_matrix_duration(
            op.get("duration_formula",
                   op.get("duration_min", op.get("duration",
                                                 op.get("minutes", 0)))), ctx
        )
        try:
            workorder = self.env["mrp.workorder"].create(
                {
                    "name": op.get("name", workcenter.name),
                    "production_id": self.id,
                    "workcenter_id": workcenter.id,
                    "product_uom_id": self.product_uom_id.id,
                    "qty_production": self.product_qty,
                    "duration_expected": duration,
                }
            )
        except Exception as exc:  # noqa: BLE001 — T3 ред не бива да чупи confirm
            _logger.warning(
                "T3 workorder create failed for %s (wc=%s): %s — skipped.",
                self.name, workcenter.display_name, exc)
            return
        # Consume the raw materials at this operation (first WO collects them).
        move_model = self.env["stock.move"]
        if "workorder_id" in move_model._fields:
            moves = self.move_raw_ids.filtered(lambda m: not m.workorder_id)
            if moves:
                try:
                    moves.write({"workorder_id": workorder.id})
                except Exception as exc:  # noqa: BLE001
                    _logger.debug("Raw moves → workorder link skipped: %s", exc)

    @staticmethod
    def _eval_matrix_duration(raw, ctx):
        """Resolve a T3 duration (minutes): number, numeric string, or a
        plain-Python expression evaluated against the matrix context.

        Plain ``exec`` (not safe_eval) — the formula is internal matrix data,
        and safe_eval rejects/zeroes such expressions on some builds."""
        if isinstance(raw, (int, float)):
            return float(raw)
        expr = str(raw or "").strip()
        if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
            expr = expr[1:-1].strip()
        try:
            return float(expr)
        except ValueError:
            pass
        try:
            scope = {"__builtins__": {
                "int": int, "float": float, "min": min, "max": max,
                "round": round, "abs": abs,
            }}
            local = dict(ctx or {})
            exec(compile("__dur__ = " + expr, "<t3_duration>", "exec"), scope, local)
            return float(local.get("__dur__", 0.0) or 0.0)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("T3 duration eval failed (%s): %s", expr, exc)
            return 0.0
