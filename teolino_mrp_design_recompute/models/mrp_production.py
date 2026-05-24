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
        lot = self._teolino_get_design_lot()
        if not lot:
            return
        rich = lot.read(["design_params"])[0].get("design_params") or []
        # Pass per-shutter pairs so the BoM simulate evaluates width/height-
        # dependent formulas per panel (slat cuts at different L per shutter).
        per_pairs = []
        if hasattr(lot, "teolino_get_per_shutter_pairs"):
            per_pairs = lot.teolino_get_per_shutter_pairs()
        sim = self.bom_id.simulate_with_params(rich, self.product_qty or 1.0, per_shutter_pairs=per_pairs)
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
