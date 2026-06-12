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


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_assign(self, force_qty=False):
        """Налага per-lot количествата от формулата.

        Базовият stock_move_forced_lot_multi пълни само празни move
        line-ове (и дели pro-rata), а core резервацията може да е взела
        всичко от един лот. Когато формулата е задала точни количества
        (``forced_lots = {lot: qty}``), тук привеждаме line-овете 1:1
        към mapping-а: коригираме, създаваме липсващи, махаме чуждите.
        """
        res = super()._action_assign(force_qty=force_qty)
        for move in self:
            mapping = (move.forced_lot_extra_data or {}).get(
                "formula_lot_qty"
            )
            if not mapping or not move.forced_lot_ids:
                continue
            lines_by_lot = {}
            for line in move.move_line_ids:
                if line.lot_id:
                    lines_by_lot.setdefault(line.lot_id.id, line)
            # 1) чужди лотове (извън mapping) → махат се
            for lot_id, line in list(lines_by_lot.items()):
                if str(lot_id) not in mapping:
                    line.unlink()
                    del lines_by_lot[lot_id]
            # 2) mapping лотове → точното количество (create при липса)
            for lot_id_str, qty in mapping.items():
                lot_id = int(lot_id_str)
                line = lines_by_lot.get(lot_id)
                if line:
                    if line.quantity != qty:
                        line.quantity = qty
                    continue
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                        "picking_id": move.picking_id.id,
                        "lot_id": lot_id,
                        "quantity": qty,
                        "company_id": move.company_id.id,
                    }
                )
        return res
