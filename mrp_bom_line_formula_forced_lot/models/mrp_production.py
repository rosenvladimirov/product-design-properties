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
from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _apply_formula_extras_to_move_values(self, values, result, bom_line):
        """Прилага формулните ``forced_lots`` върху raw move стойностите.

        - ``forced_lots`` → ``forced_lot_ids`` на move-а (резервацията на
          stock_move_forced_lot_multi после пълни move line-овете);
        - ``forced_lot_qty`` → JSON в ``forced_lot_extra_data`` — нашият
          ``stock.move._action_assign`` override разпределя количествата
          по лотове вместо pro-rata делението на базовия модул.
        """
        values = super()._apply_formula_extras_to_move_values(
            values, result, bom_line
        )
        lot_ids = result.get("forced_lots")
        if not lot_ids:
            return values
        values["forced_lot_ids"] = [(6, 0, list(lot_ids))]
        lot_qty = result.get("forced_lot_qty")
        if lot_qty:
            extra = dict(values.get("forced_lot_extra_data") or {})
            # JSON ключовете са текст
            extra["formula_lot_qty"] = {
                str(lot_id): qty for lot_id, qty in lot_qty.items()
            }
            values["forced_lot_extra_data"] = extra
        return values
