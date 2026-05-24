"""Live BoM simulation: evaluate quantity_formula on each BoM line against a
flat params dict (server-side equivalent of recompute_mo_v2.py).  Used by:
  - mrp.production.action_confirm hook → auto-set raw move qty after MO create
  - sale_design_configurator RPC → live preview while user types in dialog
"""
import logging
import math

from odoo import api, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# ⚠ DUPLICATION WARNING ⚠
# Per-model T1 geometry outputs (Python re-impl of Rosen's matrix_template T1
# because the server's zen-engine pip package is broken).  Source:
# mrp_design_matrix_teolino_shutters/data/matrix_templates.xml T1 rules.
#
# !!! CANONICAL SOURCE: mrp_design_matrix_teolino_shutters/data/matrix_templates.xml
# (geometry_table → 10 rules за 5 модела × 2 slat sizes).  Този dict е
# Python мирор за production environments където zen-engine не е installable.
#
# TODO: ако zen-engine се поправи на prod (виж feedback за pip install
# проблема), замени тоя hardcoded dict с runtime eval през
# `mrp.matrix.template._eval_t1_geometry()`.  Дотогава: всяка промяна на
# T1 rules в XML seed-а трябва ръчно да се отрази тук — иначе drift.
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

    # Exception classes referenced by `except Exception:` clauses inside
    # BoM formulas — safe_eval's builtin allowlist excludes them, so we
    # inject them into the eval namespace to keep try/except guards working.
    _TEOLINO_EVAL_EXCEPTIONS = {
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "ZeroDivisionError": ZeroDivisionError,
        "KeyError": KeyError,
        "AttributeError": AttributeError,
    }

    def _teolino_eval_formula(self, formula, ns):
        """Run a single formula against a single namespace; returns float qty.

        Most BoM lines wrap their body in ``try/except Exception:`` so the
        formula gracefully returns 0 when a referenced var is missing (e.g.
        T1 outputs).  safe_eval's builtin allowlist does not expose those
        exception classes by default — we inject them so the guards work
        instead of falling through to NameError and silently giving 0 for
        every line."""
        if not formula:
            return None
        try:
            local = dict(ns)
            local.update(self._TEOLINO_EVAL_EXCEPTIONS)
            safe_eval(formula, globals_dict=local, mode="exec", nocopy=True)
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
            if not formula:
                qty = bom_line.product_qty
            elif use_per_shutter and self._teolino_formula_uses_dims(formula):
                # Per-panel eval: width/height become panel-specific, sum
                # of per-panel quantities is the assembly total.
                qty = 0.0
                for (l_i, h_i) in per_shutter_pairs[:sc]:
                    panel_ns = dict(base_ns)
                    panel_ns["width"] = l_i
                    panel_ns["height"] = h_i
                    val = self._teolino_eval_formula(formula, panel_ns)
                    qty += (val or 0.0)
            else:
                # Constant or sc-only formula → evaluate once with assembly ns.
                qty = self._teolino_eval_formula(formula, base_ns)
                if qty is None:
                    qty = bom_line.product_qty
            if qty is None or qty < 0:
                qty = 0.0
            unit_cost = bom_line.product_id.standard_price or 0.0
            subtotal = qty * unit_cost
            total_material += subtotal
            if qty > 0:
                active += 1
            out_lines.append({
                "bom_line_id": bom_line.id,
                "product_id": bom_line.product_id.id,
                "product_name": bom_line.product_id.display_name,
                "qty": qty,
                "uom": bom_line.product_uom_id.name,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
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
