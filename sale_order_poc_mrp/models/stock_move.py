# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _adjust_procure_method(self, picking_type_code=False):
        res = super()._adjust_procure_method(picking_type_code=picking_type_code)
        # компонент с флага се взема от склада и не ражда под-MO по POC
        self.filtered(
            lambda m: m.bom_line_id.force_mts and m.procure_method == "make_to_order"
        ).procure_method = "make_to_stock"
        return res
