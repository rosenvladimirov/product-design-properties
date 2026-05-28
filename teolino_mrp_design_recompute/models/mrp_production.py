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

    def teolino_report_data(self):
        """Връща data dict за QWeb template `report_teolino_mrp_cut_list`.

        Очаквана структура от template-а:
            {
              'lot': stock.lot или False,
              'spec': {label: value, ...},
              'panels': [{'index': int, 'L_mm': int, 'H_mm': int}, ...],
              'lines': [
                {'bom_line_id': int, 'product_name': str, 'qty': float,
                 'uom': str, 'cuts': [{'panel': int, 'n_pieces': int|None,
                                       'piece_length_mm': int|None}, ...]},
                ...
              ],
              'total_material': float,
            }

        Минималната версия не fail-ва при липсващи design_params/lot/BoM —
        template-ът рендерира с празни секции вместо AttributeError.
        """
        self.ensure_one()
        lot = self._teolino_get_design_lot()

        # 1) spec — извличаме labels от lot.design_params (list of dicts)
        spec = {}
        if lot:
            for entry in (lot.read(['design_params'])[0].get('design_params') or []):
                if isinstance(entry, dict):
                    k = entry.get('label') or entry.get('name') or entry.get('code')
                    v = entry.get('value')
                    if k and v is not None:
                        spec[str(k)] = v

        # 2) panels — per-shutter L×H pairs
        panels = []
        if lot and hasattr(lot, 'teolino_get_per_shutter_pairs'):
            try:
                for idx, pair in enumerate(lot.teolino_get_per_shutter_pairs() or [], 1):
                    L = pair[0] if isinstance(pair, (list, tuple)) and len(pair) > 0 else None
                    H = pair[1] if isinstance(pair, (list, tuple)) and len(pair) > 1 else None
                    panels.append({'index': idx, 'L_mm': L, 'H_mm': H})
            except Exception as exc:
                _logger.debug("teolino_report_data: panels build failed: %s", exc)

        # 3) lines — от simulate_with_params (вкл. per-panel cuts), fallback от move_raw_ids
        sim_by_bom_line = {}
        total_material = 0.0
        if self.bom_id and lot:
            try:
                rich = lot.read(['design_params'])[0].get('design_params') or []
                per_pairs = []
                if hasattr(lot, 'teolino_get_per_shutter_pairs'):
                    per_pairs = lot.teolino_get_per_shutter_pairs() or []
                sim = self.bom_id.simulate_with_params(
                    rich, self.product_qty or 1.0, per_shutter_pairs=per_pairs,
                )
                for ln in (sim.get('lines') or []):
                    sim_by_bom_line[ln.get('bom_line_id')] = ln
                total_material = sim.get('total_material') or 0.0
            except Exception as exc:
                _logger.warning(
                    "teolino_report_data simulate failed for %s: %s", self.name, exc,
                )

        lines = []
        for move in self.move_raw_ids:
            bl_id = move.bom_line_id.id if move.bom_line_id else move.id
            sim_ln = sim_by_bom_line.get(bl_id, {})
            cuts = []
            for cut in (sim_ln.get('cuts') or []):
                cuts.append({
                    'panel': cut.get('panel') or cut.get('index'),
                    'n_pieces': cut.get('n_pieces'),
                    'piece_length_mm': cut.get('piece_length_mm') or cut.get('length_mm'),
                })
            lines.append({
                'bom_line_id': bl_id,
                'product_name': move.product_id.display_name,
                'qty': sim_ln.get('qty', move.product_uom_qty),
                'uom': move.product_uom.name if move.product_uom else '',
                'cuts': cuts,
            })

        return {
            'lot': lot or False,
            'spec': spec,
            'panels': panels,
            'lines': lines,
            'total_material': total_material,
        }

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
