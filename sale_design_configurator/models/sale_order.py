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


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """При потвърждаване на поръчката дизайн лотовете в draft минават в
        sales_confirmed (заключват sales параметрите и подават към техническото).
        Дотогава този преход ставаше само ръчно с бутона на лота.
        """
        res = super()._action_confirm()
        design_lots = self.order_line.design_lot_id.filtered(
            lambda lot: lot.design_state == "draft"
        )
        if design_lots:
            design_lots.action_design_sales_confirm()
        return res
