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
from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    teolino_per_shutter_dims = fields.Char(
        string="Per-shutter dimensions",
        help=(
            "When shutter_count > 1, stores per-shutter L×H pairs as "
            "'L1xH1,L2xH2,...' (e.g. '1000x2000,800x2500').  Read by "
            "mrp.bom.simulate_with_params to evaluate BoM formulas once "
            "per panel and sum the per-line quantities, so a 2-panel "
            "shutter produces two slat cuts in different lengths instead "
            "of one big cut at the total width."
        ),
    )

    def teolino_get_per_shutter_pairs(self):
        """Parse teolino_per_shutter_dims into [(L,H), ...].  Returns []
        when missing/empty/invalid — callers fall back to single-shutter
        eval using lot.width / lot.height."""
        self.ensure_one()
        raw = (self.teolino_per_shutter_dims or "").strip()
        if not raw:
            return []
        out = []
        for chunk in raw.split(","):
            chunk = chunk.strip().lower().replace("х", "x")
            if not chunk or "x" not in chunk:
                continue
            l_s, h_s = chunk.split("x", 1)
            try:
                out.append((float(l_s), float(h_s)))
            except ValueError:
                continue
        return out
