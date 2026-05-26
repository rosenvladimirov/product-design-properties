"""Auto-recompute raw move quantities after MO confirm.

Hooks into mrp.production.action_confirm and replaces every move's
product_uom_qty using mrp.bom.simulate_with_params() (the same engine the
configurator uses for live preview).  Eliminates the need to run
recompute_mo_v2.py manually after each SO confirm.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        res = super().action_confirm()
        for production in self:
            try:
                production._teolino_recompute_raw_moves()
            except Exception as exc:
                _logger.warning(
                    "Teolino recompute failed for %s: %s",
                    production.name, exc,
                )
        return res

    def _teolino_get_design_lot(self):
        """Locate the design lot via lot_producing_id, then via SO line."""
        self.ensure_one()
        lot = self.lot_producing_id
        if lot:
            return lot
        for move in self.move_dest_ids:
            sline = getattr(move, "sale_line_id", False)
            if sline and getattr(sline, "design_lot_id", False):
                return sline.design_lot_id
            grp = move.group_id
            if grp and getattr(grp, "sale_id", False):
                for sl in grp.sale_id.order_line:
                    if getattr(sl, "design_lot_id", False):
                        return sl.design_lot_id
        return self.env["stock.lot"]

    def _teolino_recompute_raw_moves(self):
        self.ensure_one()
        if not self.bom_id:
            return
        sim = self._teolino_simulate_for_report()
        if not sim:
            return
        qty_by_bom_line = {ln["bom_line_id"]: ln["qty"] for ln in sim["lines"]}
        updated = 0
        for move in self.move_raw_ids:
            bom_line = move.bom_line_id
            if not bom_line:
                continue
            qty = qty_by_bom_line.get(bom_line.id)
            if qty is None:
                continue
            if abs(qty - move.product_uom_qty) > 0.0001:
                move.product_uom_qty = qty
                updated += 1
        if updated:
            _logger.info(
                "Teolino recompute: updated %d/%d raw moves on %s (material total=%.2f)",
                updated, len(self.move_raw_ids), self.name, sim["total_material"],
            )

    # ── Cutting-list report data ────────────────────────────────────────
    # Helper used both by the auto-recompute hook AND by the QWeb PDF
    # "Cutting List" report.  Returns the simulate breakdown OR False when
    # the production has no BoM/lot.

    def _teolino_simulate_for_report(self):
        self.ensure_one()
        if not self.bom_id:
            return False
        lot = self._teolino_get_design_lot()
        if not lot:
            return False
        rich = lot.read(["design_params"])[0].get("design_params") or []
        per_pairs = []
        if hasattr(lot, "teolino_get_per_shutter_pairs"):
            per_pairs = lot.teolino_get_per_shutter_pairs()
        return self.bom_id.simulate_with_params(
            rich, self.product_qty or 1.0, per_shutter_pairs=per_pairs,
        )

    def teolino_report_data(self):
        """Bundle everything the cutting-list PDF needs into one dict so
        the QWeb template doesn't need to read scattered fields.

        Returns ::

            {
                "mo": self,                 # mrp.production browse record
                "lot": stock.lot or None,
                "spec": {  # display-ready spec rows
                    "shutter_model": "Standard",
                    "box_size": "165",
                    "slat_size": "40 mm",
                    "axis_size": "Axis 40",
                    "control_type": "Cord",
                    "guide_type": "Standard guide",
                    "shutter_count": 2,
                    "main_color": "001 — RAL 9016",
                },
                "panels": [             # per-panel L×H if sc>1
                    {"index": 1, "L_mm": 1200, "H_mm": 2000},
                    ...
                ],
                "lines": [...],         # from simulate_with_params
                "total_material": float,
            }
        """
        self.ensure_one()
        lot = self._teolino_get_design_lot()
        sim = self._teolino_simulate_for_report() or {
            "lines": [], "total_material": 0.0,
            "active_count": 0, "total_count": 0, "panels": 1,
        }
        spec = {}
        panels = []
        if lot:
            rich = lot.read(["design_params"])[0].get("design_params") or []
            # Selection labels for human-readable rendering
            for prop in rich:
                if not isinstance(prop, dict):
                    continue
                name = prop.get("name")
                value = prop.get("value")
                if value in (None, False, "", "use_main"):
                    continue
                label = prop.get("string") or name
                if prop.get("type") == "selection":
                    for code, human in prop.get("selection") or []:
                        if code == value:
                            value = human
                            break
                spec[label] = value
            if hasattr(lot, "teolino_get_per_shutter_pairs"):
                pairs = lot.teolino_get_per_shutter_pairs()
                for idx, (L, H) in enumerate(pairs):
                    panels.append({
                        "index": idx + 1,
                        "L_mm": int(L),
                        "H_mm": int(H),
                    })
        return {
            "mo": self,
            "lot": lot,
            "spec": spec,
            "panels": panels,
            "lines": [l for l in sim["lines"] if l["qty"] > 0],
            "total_material": sim["total_material"],
        }
