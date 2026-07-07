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

        20.0 вариант: UUID → schema ``string`` + selection display→raw
        обръщане (без formula_name / legacy alias слоеве, които са 19.0).
        """
        extra = extra or {}
        ctx = {
            "width": extra.get("width", 0.0),
            "height": extra.get("height", 0.0),
            "thickness": extra.get("thickness", 0.0),
        }

        # Build UUID → (string_name, display→raw) mapping from schema.
        definition = self
        uuid_map = {}
        if definition:
            schema = definition.full_design_params_definition or []
            for prop in schema:
                if not isinstance(prop, dict):
                    continue
                uuid = prop.get("name")
                if not uuid:
                    continue
                string_name = prop.get("string") or uuid
                # Reverse map for selection: {display_label: raw_value}
                reverse = {}
                for entry in (prop.get("selection") or []):
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        raw, label = entry
                        reverse[label] = raw
                uuid_map[uuid] = (string_name, reverse)

        for key, value in (params or {}).items():
            string_name, reverse = uuid_map.get(key, (key, {}))
            # Reverse lookup display → raw for selection values only.
            raw_value = reverse.get(value, value) if reverse else value
            ctx[string_name] = raw_value
        return ctx
