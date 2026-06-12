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


class MRPBomLine(models.Model):
    _inherit = "mrp.bom.line"

    def _quantity_formula_values(self, *args, **kwargs):
        """Добавя лотов контекст към формулата:

        - ``lot_model`` — моделът ``stock.lot`` (search/browse);
        - ``mo_forced_lots`` — форсираните лотове на MO-то, филтрирани
          до продукта на реда (когато базовият модул е добавил полето).
        """
        values = super()._quantity_formula_values(*args, **kwargs)
        values["lot_model"] = self.env["stock.lot"]
        production = values.get("production")
        product = values.get("product")
        mo_lots = self.env["stock.lot"]
        if production and "forced_lot_ids" in production._fields:
            mo_lots = production.forced_lot_ids
            if product:
                mo_lots = mo_lots.filtered(
                    lambda l: l.product_id == product
                )
        values["mo_forced_lots"] = mo_lots
        return values

    def _quantity_formula_extra_outputs(self, values):
        """Чете ``forced_lots`` от формулата.

        Поддържани форми::

            forced_lots = lot_model.search([...])          # recordset
            forced_lots = [lot_a, lot_b]                   # списък
            forced_lots = {lot_a: 3.0, lot_b: 1.5}         # лот → количество
        """
        extra = super()._quantity_formula_extra_outputs(values)
        forced = values.get("forced_lots")
        if not forced:
            return extra

        lot_ids = []
        lot_qty = {}
        if isinstance(forced, dict):
            for lot, qty in forced.items():
                ids = lot.ids if hasattr(lot, "ids") else [lot]
                for lot_id in ids:
                    lot_ids.append(lot_id)
                    try:
                        lot_qty[lot_id] = float(qty)
                    except (TypeError, ValueError):
                        _logger.warning(
                            "Formula of BoM line %s: non-numeric quantity "
                            "(%r) for forced lot %s — ignored.",
                            self.id, qty, lot_id,
                        )
        else:
            for item in forced if isinstance(forced, (list, tuple)) else [forced]:
                if hasattr(item, "ids"):
                    lot_ids.extend(item.ids)
                elif isinstance(item, int):
                    lot_ids.append(item)

        if lot_ids:
            extra["forced_lots"] = lot_ids
            if lot_qty:
                extra["forced_lot_qty"] = lot_qty
        return extra
