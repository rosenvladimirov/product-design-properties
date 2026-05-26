"""Live BoM simulation: evaluate quantity_formula on each BoM line against a
flat params dict (server-side equivalent of recompute_mo_v2.py).  Used by:
  - mrp.production.action_confirm hook → auto-set raw move qty after MO create
  - sale_design_configurator RPC → live preview while user types in dialog

NOTE on eval mechanism: we use Python's plain `exec` with a sandboxed
globals dict instead of Odoo's `safe_eval`.  Investigation 2026-05-26
revealed safe_eval silently zeros every formula on Vladimir's dev-teo-2305
server even for trivial `quantity = 999` — likely a registry/cache state
unrelated to formula correctness, since the same formula bodies evaluate
fine with plain `exec` from recompute_mo_v2.py.  The BoM formulas come
from admin-only configuration, so the looser sandbox is acceptable for
this server-side eval path.
"""
import logging
import math

from odoo import api, models

_logger = logging.getLogger(__name__)

# Whitelist for the plain-exec sandbox — only data/math primitives, no
# I/O or import access.  Mirrors what recompute_mo_v2.py passes.
_TEOLINO_FORMULA_GLOBALS = {
    "__builtins__": {
        "int": int, "float": float, "abs": abs, "min": min, "max": max,
        "round": round, "len": len, "sum": sum, "any": any, "all": all,
        "True": True, "False": False, "None": None,
    },
    "math": math,
}

# Per-model T1 geometry outputs (Python re-impl of Rosen's matrix_template T1
# because the server's zen-engine pip package is broken).  Source:
# mrp_design_matrix_teolino_shutters/data/matrix_templates.xml T1 rules.
_T1_RULES = {
    "standard":      ({40: 70, 50: 76}, 72, 55, 70, 10, "std",     "n1",     "h_minus_box"),
    "round":         ({40: 70, 50: 76}, 72, 55, 70, 10, "std",     "n1",     "h_minus_box"),
    "t_roll":        ({40: 90, 50: 90}, 92, 90, 90, 10, "std",     "n1",     "fixed_pvc"),
    "built_in":      ({40: 18, 50: 18}, 20, 70, 70,  0, "builtin", "equal",  "h_minus_1"),
    "thermo_comfort":({40: 70, 50: 76}, 72, 55, 70, 15, "thermo",  "direct", "thermo_sel"),
}


def _t1_outputs(model, slat):
    rule = _T1_RULES.get(model)
    if not rule:
        return {}
    slat_off_map, term_off, a40, a60, box_off, slat_mode, caps_mode, guide_mode = rule
    slat_i = int(slat) if str(slat).isdigit() else 40
    return {
        "slat_len_offset": slat_off_map.get(slat_i, 70),
        "terminal_offset": term_off,
        "axis_off_40": a40,
        "axis_off_60": a60,
        "box_form_offset": box_off,
        "slat_count_mode": slat_mode,
        "caps_mode": caps_mode,
        "guide_mode": guide_mode,
    }


_LABEL_TO_DIM = {
    "Width (mm)": "width",
    "Height (mm)": "height",
    "Thickness (mm)": "thickness",
}


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _teolino_build_namespace(self, design_params_rich, product_uom_qty=1.0):
        """Flatten rich design_params (Properties list) into formula namespace.

        Maps Width(mm)/Height(mm) labels → flat width/height keys, exposes
        both UUID `name` and human `string` keys, then adds T1 outputs.
        """
        ns = {
            "width": 0,
            "height": 0,
            "thickness": 0,
            "shutter_model": "standard",
            "box_size": "137",
            "slat_size": "40",
            "axis_size": "40",
            "control_type": "rope",
            "guide_type": "standard",
            "shutter_count": "1",
            "main_color": "001",
            "product_uom_qty": product_uom_qty,
            "math": math,
        }
        for prop in (design_params_rich or []):
            if not isinstance(prop, dict):
                continue
            name = prop.get("name")
            value = prop.get("value")
            label = prop.get("string") or ""
            if value is None:
                continue
            if name:
                ns[name] = value
            if label:
                ns[label] = value
                dim = _LABEL_TO_DIM.get(label)
                if dim:
                    ns[dim] = value
        # T1 outputs (depend on model + slat)
        ns.update(_t1_outputs(ns["shutter_model"], ns["slat_size"]))
        return ns

    # Legacy compat alias — older formula bodies / callers may still
    # reference this dict.  Plain exec has all Python exception classes in
    # scope automatically, so this stays empty.
    _TEOLINO_EVAL_EXCEPTIONS = {}

    def _teolino_eval_formula_into(self, formula, ns):
        """Eval formula MUTATING ns (so callers can read out intermediates
        like ``n_pieces`` / ``piece_length_mm`` for the cutting list)."""
        if not formula:
            return None
        try:
            exec(formula, _TEOLINO_FORMULA_GLOBALS, ns)
            return float(ns.get("quantity", ns.get("result", 0)) or 0)
        except Exception as exc:
            _logger.warning("Formula eval (into) failed: %s | expr=%s", exc, formula[:120])
            return 0.0

    def _teolino_eval_formula(self, formula, ns):
        """Run a single formula against a single namespace; returns float qty.
        Plain Python exec with a primitive-only globals sandbox — see the
        module docstring for why we don't use safe_eval here."""
        if not formula:
            return None
        try:
            local = dict(ns)
            exec(formula, _TEOLINO_FORMULA_GLOBALS, local)
            return float(local.get("quantity", local.get("result", 0)) or 0)
        except Exception as exc:
            _logger.warning("Formula eval failed: %s | expr=%s", exc, formula[:120])
            return 0.0

    @staticmethod
    def _teolino_formula_uses_dims(formula):
        """True when the formula references panel-specific dimensions.
        Per-shutter eval mode is enabled only for such lines — constant /
        sc-only formulas (caps=50, end_caps=2, central_caps=sc-1) stay as
        single-pass evals so they aren't multiplied by panel count."""
        return ("width" in formula) or ("height" in formula)

    def _teolino_resolve_variant(self, bom_line, ns):
        """Walk ``bom_line.param_attribute_map`` to find the actual color
        variant whose ``default_code`` suffix matches the design param
        value (e.g. for ``color_slat='006'``, return the variant of the
        Slat 50 template whose default_code ends in ``-006``).  Falls back
        to ``bom_line.product_id`` when there's no mapping or no match.

        Fixes 2026-05-26 issue: live preview / cutting-list PDF showed
        the placeholder variant name + price (always color 001) instead
        of the customer-chosen color, because the engine read
        ``bom_line.product_id`` directly and skipped PTAV resolution.
        """
        pam = bom_line.param_attribute_map or {}
        if not pam:
            return bom_line.product_id
        for param_key, _attr_xml_id in pam.items():
            color_code = ns.get(param_key)
            if not color_code or color_code == "use_main":
                continue
            tmpl_id = bom_line.product_id.product_tmpl_id.id
            variant = self.env["product.product"].search([
                ("product_tmpl_id", "=", tmpl_id),
                ("default_code", "=like", f"%-{color_code}"),
            ], limit=1)
            if variant:
                return variant
        return bom_line.product_id

    def simulate_with_params(self, design_params_rich, product_uom_qty=1.0, per_shutter_pairs=None):
        """Evaluate every active BoM line's quantity_formula against the
        provided design params.  When per_shutter_pairs is given (list of
        (L, H) tuples) AND shutter_count > 1, each formula is evaluated
        ONCE PER PANEL with (width, height) overridden, and the per-line
        quantities are summed.  This models the BoM correctly for 2/3/4-
        shutter assemblies that share a single box but have independent
        slat cuts and guide lengths.

        :param design_params_rich: list of {name, type, string, value, ...}
        :param product_uom_qty: production qty (default 1)
        :param per_shutter_pairs: optional [(L, H), ...]; when omitted, the
                                  formula is evaluated once with the lot's
                                  flat width/height (back-compat for single
                                  shutter or older lots without per-shutter
                                  data).
        :returns: {
            "lines": [{"product_id", "product_name", "qty", "uom", "unit_cost", "subtotal"}, ...],
            "total_material": float,
            "active_count": int,
            "total_count": int,
            "panels": int,  # how many shutters were eval'd (1 = no split)
        }
        """
        self.ensure_one()
        base_ns = self._teolino_build_namespace(design_params_rich, product_uom_qty)
        # Pick eval mode: per-shutter loop or single pass
        sc = 1
        try:
            sc = int(base_ns.get("shutter_count") or 1)
        except (TypeError, ValueError):
            sc = 1
        use_per_shutter = bool(per_shutter_pairs) and sc > 1 and len(per_shutter_pairs) >= sc
        out_lines = []
        total_material = 0.0
        active = 0
        for bom_line in self.bom_line_ids:
            formula = (bom_line.quantity_formula or "").strip()
            cuts = []  # per-panel breakdown for the cutting list (slats, etc.)
            if not formula:
                qty = bom_line.product_qty
            elif use_per_shutter and self._teolino_formula_uses_dims(formula):
                # Per-panel eval: width/height become panel-specific, sum
                # of per-panel quantities is the assembly total.  Capture
                # n_slats + computed cut length so the UI can render the
                # production cutting list ("N бр × L mm на платно").
                qty = 0.0
                for idx, (l_i, h_i) in enumerate(per_shutter_pairs[:sc]):
                    panel_ns = dict(base_ns)
                    panel_ns.update(self._TEOLINO_EVAL_EXCEPTIONS)
                    panel_ns["width"] = l_i
                    panel_ns["height"] = h_i
                    val = self._teolino_eval_formula_into(formula, panel_ns)
                    qty += (val or 0.0)
                    if val and val > 0:
                        # Formula-author hints take precedence — refactored
                        # formulas set both `n_pieces` (count per panel) and
                        # `piece_length_mm` (None when the part has no cut
                        # length, e.g. caps that are stuck onto slats).
                        n_pieces = panel_ns.get("n_pieces")
                        if n_pieces is None:
                            n_pieces = panel_ns.get("n_slats")  # legacy
                        piece_len = panel_ns.get("piece_length_mm", "__SENTINEL__")
                        if piece_len == "__SENTINEL__":
                            # Legacy fallback: derive from slat_len_offset.
                            off = panel_ns.get("slat_len_offset") or 0
                            piece_len = None
                            if n_pieces is not None:
                                try:
                                    piece_len = max(0, int(l_i - int(off)))
                                except (TypeError, ValueError):
                                    piece_len = None
                        cuts.append({
                            "panel": idx + 1,
                            "L_mm": int(l_i),
                            "H_mm": int(h_i),
                            "qty_per_panel": float(val),
                            "n_pieces": int(n_pieces) if n_pieces is not None else None,
                            "piece_length_mm": int(piece_len) if piece_len is not None else None,
                        })
            else:
                # Constant or sc-only formula → evaluate once with assembly ns.
                qty = self._teolino_eval_formula(formula, base_ns)
                if qty is None:
                    qty = bom_line.product_qty
            if qty is None or qty < 0:
                qty = 0.0
            # Resolve placeholder → actual color variant for display + price.
            actual = self._teolino_resolve_variant(bom_line, base_ns)
            unit_cost = actual.standard_price or 0.0
            subtotal = qty * unit_cost
            total_material += subtotal
            if qty > 0:
                active += 1
            out_lines.append({
                "bom_line_id": bom_line.id,
                "product_id": actual.id,
                "product_name": actual.display_name,
                "qty": qty,
                "uom": bom_line.product_uom_id.name,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "cuts": cuts,
            })
        return {
            "lines": out_lines,
            "total_material": total_material,
            "active_count": active,
            "total_count": len(out_lines),
            "panels": (sc if use_per_shutter else 1),
        }

    @api.model
    def simulate_for_product(self, product_tmpl_id, design_params_rich, product_uom_qty=1.0, per_shutter_pairs=None):
        """Lookup BoM by product_tmpl_id and run simulate_with_params."""
        bom = self.search([("product_tmpl_id", "=", product_tmpl_id), ("active", "=", True)], limit=1)
        if not bom:
            return {"lines": [], "total_material": 0.0, "active_count": 0, "total_count": 0,
                    "error": "No active BoM for product_tmpl_id %s" % product_tmpl_id}
        return bom.simulate_with_params(design_params_rich, product_uom_qty, per_shutter_pairs=per_shutter_pairs)

    @api.model
    def simulate_for_variant(self, product_id, design_params_rich, product_uom_qty=1.0, per_shutter_pairs=None):
        """Accept product.product id (configurator dialog passes variant id)."""
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            return {"lines": [], "total_material": 0.0, "active_count": 0, "total_count": 0,
                    "error": "Product variant %s not found" % product_id}
        return self.simulate_for_product(product.product_tmpl_id.id, design_params_rich, product_uom_qty, per_shutter_pairs=per_shutter_pairs)
