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

from odoo import models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def design_cutlist_data(self):
        """Данни за QWeb cut-list (Спецификация за рязане) — Теолино патърн,
        адаптиран за вратите. Само ЧЕТЕ; защитно (празни секции при липси).

        Връща: {production, lot, spec:[{label,value}], lines:[<simulate
        lines>], total_material}.
        """
        self.ensure_one()
        bom = self.bom_id
        # Odoo 19: lot_producing_ids (мн.ч.); първият лот = design лотът.
        lot = self.env["stock.lot"]
        if "lot_producing_ids" in self._fields and self.lot_producing_ids:
            lot = self.lot_producing_ids[:1]

        ctx = {}
        if lot and hasattr(lot, "_get_design_context"):
            try:
                ctx = lot._get_design_context()
            except Exception as exc:  # noqa: BLE001
                _logger.debug("cutlist ctx failed for %s: %s", self.name, exc)

        cost = {}
        if bom:
            try:
                # sudo: cut-list е производствен документ (количества за рязане) —
                # печата се и от не-мениджъри; cost gate-ът иначе би върнал празни
                # редове (AccessError глътнат от except-а).
                cost = bom.sudo().simulate_design_cost(ctx, self.product_qty or 1.0)
            except Exception as exc:  # noqa: BLE001
                _logger.debug("cutlist simulate failed for %s: %s", self.name, exc)
        # Методът е публичен (RPC) → БЕЗ пари за не-мениджъри: PDF-ът ползва само
        # product_name/qty/uom/loss; unit_cost/subtotal/total_material течаха по RPC.
        try:
            self.env["mrp.bom"]._ensure_design_cost_access()
            money_ok = True
        except Exception:  # noqa: BLE001 — AccessError → без пари
            money_ok = False
        line_keys = ("product_name", "qty", "uom", "loss") + (
            ("unit_cost", "subtotal", "price_source") if money_ok else ())
        cost["lines"] = [
            {k: ln.get(k) for k in line_keys if k in ln}
            for ln in cost.get("lines", [])
        ]
        if not money_ok:
            cost["total_material"] = 0.0

        # Спецификация: четими параметри (selection → етикет на стойността).
        spec = []
        if lot:
            try:
                params = lot.read(["design_params"])[0].get("design_params") or []
                for entry in params:
                    if not isinstance(entry, dict) or not entry.get("string"):
                        continue
                    val = entry.get("value")
                    if entry.get("type") == "selection" and val:
                        val = dict(entry.get("selection") or []).get(val, val)
                    if val in (None, "", False):
                        continue
                    spec.append({"label": entry["string"], "value": val})
            except Exception as exc:  # noqa: BLE001
                _logger.debug("cutlist spec failed for %s: %s", self.name, exc)

        return {
            "production": self,
            "lot": lot or False,
            "spec": spec,
            "lines": cost.get("lines", []),
            "total_material": cost.get("total_material", 0.0),
        }
