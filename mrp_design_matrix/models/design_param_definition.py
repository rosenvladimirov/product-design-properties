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


class DesignParamDefinition(models.Model):
    _inherit = "design.param.definition"

    def _build_context(self, params, extra=None):
        """Резолвва flat design context от параметри срещу тази дефиниция.

        Единственият резолвер за design context — ползван и от ``stock.lot``,
        и от ``mrp.production`` (MO-конфигурацията в
        ``mrp_design_matrix_production``), за да дават ИДЕНТИЧЕН контекст.

        ``self`` = ``design.param.definition`` (може да е празен recordset —
        тогава се връщат само размерите/изборите + суровите параметри).
        ``params`` = ``design_params`` dict (UUID → стойност).
        ``extra`` = по избор ``{"width", "height", "thickness",
        "material_choices"}`` (партидата ги подава; MO обикновено не).

        Трите декъплнати именни слоя (formula_name / string label / legacy
        alias) захранват един и същ контекст — виж историята в
        ``stock.lot._get_design_context``.
        """
        self.ensure_one() if self else None
        extra = extra or {}
        ctx = {
            "width": extra.get("width", 0.0),
            "height": extra.get("height", 0.0),
            "thickness": extra.get("thickness", 0.0),
        }

        # Build UUID → (string_name, display→raw) mapping from schema.
        definition = self
        uuid_map = {}
        uuid_to_formula = {}
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
            # UUID → canonical formula_name (merged param_dictionary).
            for fname, entry in (definition._get_merged_param_dictionary()).items():
                if isinstance(entry, dict) and entry.get("uuid"):
                    uuid_to_formula[entry["uuid"]] = fname

        def _coerce_numeric(val):
            """Char параметри с числово съдържание (КСИ H/B са char '2100')
            → число: ZEN сравненията ('> 0', '< 900') и T0/T3 иначе ТИХО не
            match-ват string (E2E находка: MO без операции, T0 без лимити).
            Selection стойностите НЕ минават оттук (кодовете остават string).
            """
            if isinstance(val, str):
                sv = val.strip().replace(",", ".")
                if sv:
                    try:
                        return float(sv)
                    except ValueError:
                        return val
            return val

        for key, value in (params or {}).items():
            string_name, reverse = uuid_map.get(key, (key, {}))
            # Reverse lookup display → raw for selection values only.
            if reverse:
                raw_value = reverse.get(value, value)
            else:
                raw_value = _coerce_numeric(value)
            ctx[string_name] = raw_value
            # Canonical formula_name layer (preferred by new formulas).
            fname = uuid_to_formula.get(key)
            if fname:
                ctx[fname] = raw_value

        # Явни избори на материал (choice_<key> → product_id).
        ctx.update(extra.get("material_choices") or {})

        # Alias expansion: legacy c_* / display names → canonical value, so
        # legacy formulas resolve from the same context. Не презаписва реални
        # ключове (alias not in ctx).
        if definition:
            for alias, fname in (definition._get_merged_legacy_aliases()).items():
                if fname in ctx and alias not in ctx:
                    ctx[alias] = ctx[fname]
        return ctx
