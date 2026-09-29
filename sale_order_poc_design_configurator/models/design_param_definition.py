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
"""Кубчето на реда показва стойностите от POC, не подразбиранията.

На черновата партида няма, затова конфигураторът тръгваше от дефиницията
(S00048, 21.09). Конфигураторът подава реда на куката на вертикала
(``design_sale_line_id`` в контекста). Ред с POC и без фиксирана дизайн
партида: стойностите на POC влизат в параметрите ПРЕДИ каскадата на
вертикала и излизат заключени — POC ги управлява, тук се гледат.

Избор от POC, различен от екрана, зарежда своите параметри, както избор на
екрана (конфигураторът вика куката при смяна на избор) — например
материалът извежда вълната си. Същият избор не ги презарежда: ръчното в
партидата оцелява.
"""

from odoo import api, models


class DesignParamDefinition(models.Model):
    _inherit = "design.param.definition"

    @api.model
    def get_param_patch(self, definition_id, changed_key, params):
        line_id = self.env.context.get("design_sale_line_id")
        line = self.env["sale.order.line"].sudo()
        if line_id:
            line = line.browse(line_id).exists()
        poc = line.poc_id
        definition = self.browse(definition_id).exists()
        # POC се чете при зареждане САМО преди дизайн партидата да е
        # фиксирана; после матрицата чете от партидата
        if not poc or not definition or line.design_lot_id:
            return super().get_param_patch(definition_id, changed_key, params)
        schema = poc._poc_matrix_schema(definition)
        uuid_of = {prop["string"]: prop["name"] for prop in schema}
        managed = {
            uuid_of[string]: value
            for string, value in poc._poc_matrix_values(schema).items()
        }
        screen = dict(params or {})
        params = {**screen, **managed}
        result = super().get_param_patch(definition_id, changed_key, params)
        locked = list(result.get("locked") or [])
        loaded = {}
        for prop in schema:
            key = prop["name"]
            if (
                prop.get("type") != "selection"
                or key not in managed
                or screen.get(key) == managed[key]
            ):
                continue
            patch = super().get_param_patch(definition_id, key, params)
            loaded.update(patch.get("values") or {})
            locked += [k for k in patch.get("locked") or [] if k not in locked]
        values = {**loaded, **(result.get("values") or {}), **managed}
        locked += [key for key in managed if key not in locked]
        return {**result, "values": values, "locked": locked}
