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


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    @api.model
    def simulate_cost_for_product(self, product_id, design_context=None,
                                  product_uom_qty=1.0, lot_id=False):
        """Hook (D1 инверсия): базовият UI модул дефинира интерфейса; leaf
        модулът mrp_design_matrix_cost го ИМПЛЕМЕНТИРА (зарежда се след нас →
        неговата дефиниция печели в MRO). Без cost модула конфигураторът
        получава {"available": False} и крие калкулационния панел, вместо да
        удря несъществуващ метод (RPC грешка на всяка промяна на параметър).
        """
        return {"available": False}
