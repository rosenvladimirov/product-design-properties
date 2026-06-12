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
from odoo import api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model_create_multi
    def create(self, vals_list):
        # "formula_skip" е вътрешен маркер на formula evaluation hook-а;
        # стандартната експлозия го филтрира в _get_moves_raw_values, но
        # чужди пътища (напр. Update BoM на жива MO) викат единичния
        # _get_move_raw_values директно — тук маркерът се чисти, за да не
        # стигне до ORM-а (редът остава с количество 0 в тези пътища).
        for vals in vals_list:
            vals.pop("formula_skip", None)
        return super().create(vals_list)
