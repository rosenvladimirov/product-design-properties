# Copyright 2026 Rosen Vladimirov
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

    def _get_moves_raw_values(self):
        """Разгръщането на всяка MO с конфигурация носи MO-то в контекста.

        ``mrp.bom.explode`` не знае за коя поръчка разгръща, а формулата на
        реда с кит чете конфигурацията на MO (``_skip_bom_line``). Затова
        всяка MO с POC се разгръща поотделно, със своя контекст.
        """
        with_poc = self.filtered("poc_id")
        moves = super(MrpProduction, self - with_poc)._get_moves_raw_values()
        for production in with_poc:
            moves += super(
                MrpProduction,
                production.with_context(poc_kit_production_id=production.id),
            )._get_moves_raw_values()
        return moves
