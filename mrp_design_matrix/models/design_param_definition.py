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


class DesignParamDefinition(models.Model):
    _inherit = "design.param.definition"

    def _build_context(self, params, extra=None):
        """Резолвва flat design context от параметри срещу тази дефиниция.

        Единственият резолвер — ползван от ``stock.lot`` и от
        ``mrp.production`` (MO-конфига в mrp_design_matrix_production), за да
        дават ИДЕНТИЧЕН контекст. ``self`` може да е празен recordset.

        18.0 вариант: плоско копие на параметрите (без UUID/selection слоеве —
        те са 19.0/20.0 надстройки).
        """
        extra = extra or {}
        ctx = {
            "width": extra.get("width", 0.0),
            "height": extra.get("height", 0.0),
            "thickness": extra.get("thickness", 0.0),
        }
        for key, value in (params or {}).items():
            ctx[key] = value
        return ctx
