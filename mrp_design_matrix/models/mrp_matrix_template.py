# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models

# Legacy и modern node типове — `ZenWrapper._migrate_node_types` пренаписва
# legacy → modern на runtime, така че при сканиране трябва да приемем и двата.
_T2_DECISION_TYPES = ("decisionTable", "decisionTableNode")


class MrpMatrixTemplate(models.Model):
    """
    Stores DMN rule tables (GoRules JSON format) for a specific industry.

    Templates are shipped read-only with each sub-module via data XML.
    The user copies them into a BoM with ``action_load_from_template()``
    and customises the copies — the original template is never edited.

    Table structure (GoRules JDM format stored as JSONB):
        - constraint_table : T0 — validation constraints (ERROR / WARNING)
        - geometry_table   : T1 — geometry & forced values
        - material_table   : T2 — material selection & quantities
        - operation_table  : T3 — conditional workorders
    """

    _name = "mrp.matrix.template"
    _description = "Design Matrix Template"
    _rec_name = "name"
    _order = "industry_id, name"

    name = fields.Char(required=True)
    industry_id = fields.Many2one(
        "design.industry",
        string="Industry",
        ondelete="restrict",
        index=True,
        help="Canonical industry classification. Resolved automatically "
        "from the data tag (e.g. industry=\"doors\") via "
        "design.industry._resolve — no data-file changes needed.",
    )
    description = fields.Text()

    # -- Zero-churn industry resolution --------------------------------------
    # 8-те sibling модула подават `<field name="industry">doors</field>` като
    # свободен стринг. Прехващаме го и резолваме към design.industry, така че
    # data файловете им остават непокътнати.

    @api.model
    def _pop_industry_tag(self, vals):
        """Translate a string ``industry`` key in *vals* to ``industry_id``."""
        if "industry" in vals and not isinstance(vals.get("industry"), int):
            tag = vals.pop("industry")
            industry = self.env["design.industry"].sudo()._resolve(tag)
            vals["industry_id"] = industry.id or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_industry_tag(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._pop_industry_tag(vals)
        return super().write(vals)

    constraint_table = fields.Json(
        "T0 — Constraints",
        help="GoRules JDM JSON: ERROR / WARNING rules evaluated before MO.",
    )
    geometry_table = fields.Json(
        "T1 — Geometry",
        help=(
            "GoRules JDM JSON: computes intermediate context variables. "
            "Supports context_modify, context_force and context_derive effects."
        ),
    )
    material_table = fields.Json(
        "T2 — Materials",
        help=(
            "GoRules JDM JSON: determines which materials enter the MO and "
            "in what quantities. Supports O-variant activation, direct ref "
            "and PTAV resolution."
        ),
    )
    operation_table = fields.Json(
        "T3 — Operations",
        help="GoRules JDM JSON: conditionally adds workorders to the MO.",
    )
    cascade_table = fields.Json(
        "TΦ — Cascade Resolutions",
        help=(
            "GoRules JDM JSON: reactive value propagation. Когато param X се "
            "промени → derive стойност за param Y. Output schema per rule: "
            "`target_param`, `copy_from` (другият param чиято стойност копираме), "
            "`derive_value` (explicit стойност), `only_if_empty` (bool — не overwrite-вай "
            "explicit user choice). Eval-ва се на всяка onParamChange в "
            "configurator-а. Optional layer."
        ),
    )
    availability_table = fields.Json(
        "TΠ — Param Availability",
        help=(
            "GoRules JDM JSON: reactive UI control for the design configurator. "
            "Inputs = current param context; outputs = per-param state instructions: "
            "`param`, `visible` (bool), `enabled` (bool), `allowed_values` (list, JDM string), "
            "`default_override` (any). Eval-ва се от sale_design_configurator на всяка промяна "
            "на поле — controls се hide/disable/filter според резултата. "
            "Optional layer: при празно поле configurator-ът се държи както досега."
        ),
    )

    # -- T2 coeff-key introspection -----------------------------------------
    # T2 emit-ва `bom_line_coeff_key` стойности, които mrp.bom.line.matrix_coeff_rule
    # трябва да декларира за да получи runtime coefficient. Тук extract-ваме
    # обявените от template-а ключове, за да може mrp.bom._check_t2_wiring да ги
    # сравни с реалните decларации по редовете.

    @staticmethod
    def _extract_t2_coeff_keys(table_json):
        """Return the set of distinct ``bom_line_coeff_key`` values produced
        by *table_json* — a GoRules JDM material table (dict).

        Strips the JDM string-literal quoting so ``'"motor-o"'`` се връща
        като ``'motor-o'``. Празни / None / non-string values се игнорират.
        Tolerира и двата node типа (``decisionTable`` legacy / ``decisionTableNode``
        modern).
        """
        if not isinstance(table_json, dict):
            return set()
        keys = set()
        for node in table_json.get("nodes") or []:
            if not isinstance(node, dict) or node.get("type") not in _T2_DECISION_TYPES:
                continue
            for rule in (node.get("content") or {}).get("rules") or []:
                if not isinstance(rule, dict):
                    continue
                raw = rule.get("bom_line_coeff_key")
                if not raw:
                    continue
                # JDM съхранява стрингови литерали с двойни кавички вътре в стринга:
                # `'"motor-o"'`. Декодираме само ако започва с `"`.
                value = raw
                if isinstance(raw, str) and raw.startswith('"'):
                    try:
                        value = json.loads(raw)
                    except (ValueError, TypeError):
                        value = raw
                if isinstance(value, str) and value:
                    keys.add(value)
        return keys

    def _get_t2_coeff_keys(self):
        """Convenience wrapper за template-инстанция."""
        self.ensure_one()
        return self._extract_t2_coeff_keys(self.material_table)

    # -- TΠ Param Availability evaluation -----------------------------------
    # TΠ е reactive UI слой: на всяка промяна на param стойност в design
    # configurator-а, изпращаме текущия context и получаваме per-param
    # инструкции (visible / enabled / allowed_values / default_override).
    # Engine-ът е същият (zen-engine). Обикновено hitPolicy=collect — всички
    # matching rules се натрупват и сливат в краен dict per param.

    _AVAILABILITY_KEYS = ("visible", "enabled", "allowed_values", "default_override")

    @classmethod
    def _normalize_availability(cls, raw_payload):
        """Take raw zen-engine output and produce ``{param: {visible, enabled,
        allowed_values, default_override}}``.

        Приема няколко форми на raw payload (engine ползва различни форми за
        ``hitPolicy=collect`` vs ``first``):
        - list of {"param": ..., **state} — типичен collect output
        - dict — единичен rule (first/priority)
        - dict с "result" key (legacy normalize wrapper)
        Невалидни/празни rule-ове се игнорират. По default param е visible
        и enabled — explicit ``False`` от rule overridе-ва.
        """
        items = []
        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            # ZenWrapper._normalize_payload може да върне {errors, warnings, result?}.
            # TΠ rules-ите няма да имат `level`, така че попадат в `result`.
            if "result" in raw_payload and isinstance(raw_payload["result"], list):
                items = raw_payload["result"]
            elif "param" in raw_payload:
                items = [raw_payload]
            else:
                # Възможно е engine-ът да върне dict-по-param директно
                # (custom output schema) — приемаме както е.
                return {
                    k: v for k, v in raw_payload.items()
                    if isinstance(v, dict)
                }

        out = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            param = item.get("param")
            if not param:
                continue
            state = out.setdefault(param, {})
            for key in cls._AVAILABILITY_KEYS:
                if key not in item:
                    continue
                value = item[key]
                if key == "allowed_values":
                    # Множество rules за един param → intersect-ваме (по-рестриктивно)
                    if isinstance(value, list):
                        if "allowed_values" in state and isinstance(state["allowed_values"], list):
                            state["allowed_values"] = [
                                v for v in state["allowed_values"] if v in value
                            ]
                        else:
                            state["allowed_values"] = list(value)
                elif key in ("visible", "enabled"):
                    # AND-натрупване — ако някое rule каже False, прескача True
                    if key in state:
                        state[key] = bool(state[key]) and bool(value)
                    else:
                        state[key] = bool(value)
                else:
                    # default_override — last write wins (по rule order)
                    state[key] = value
        return out

    # -- TΦ Cascade Resolutions evaluation ----------------------------------
    # TΦ е reactive cascade слой: когато param X се промени, derive стойност
    # за param Y (copy from друг param OR explicit value). Engine-ът е
    # същият (zen-engine). hitPolicy=collect — натрупване на всички matching
    # rules; _normalize_cascade ги сливa per target_param (last wins).

    _CASCADE_KEYS = ("copy_from", "derive_value", "only_if_empty")

    @classmethod
    def _normalize_cascade(cls, raw_payload):
        """Take raw zen-engine output and produce ``{target_param: {copy_from?,
        derive_value?, only_if_empty?}}``.

        Приема list (collect output), dict с "result" key (legacy wrapper),
        или single rule dict. Невалидни/празни rule-ове се игнорират.
        За multiple rules с един target_param: last write wins (rule order
        в JDM е canonical).
        """
        items = []
        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            if "result" in raw_payload and isinstance(raw_payload["result"], list):
                items = raw_payload["result"]
            elif "target_param" in raw_payload:
                items = [raw_payload]
            else:
                return {
                    k: v for k, v in raw_payload.items()
                    if isinstance(v, dict) and "target_param" not in (v or {})
                }

        out = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            target = item.get("target_param")
            if not target:
                continue
            spec = out.setdefault(target, {})
            for key in cls._CASCADE_KEYS:
                if key not in item:
                    continue
                value = item[key]
                if key == "only_if_empty":
                    spec[key] = bool(value)
                elif value not in (None, "", False):
                    spec[key] = value
        return out

    def _evaluate_cascade(self, changed_param, context):
        """Evaluate ``cascade_table`` за дадена промяна.

        :param changed_param: string — името на param-а който се промени
            (както е в DPD's ``string`` field — `shutter_model`, `main_color`).
        :param context: dict от текущите param стойности.
        :returns: dict ``{target_param: {copy_from?, derive_value?,
            only_if_empty?}}``. Празен dict ако TΦ не е дефиниран.
        """
        self.ensure_one()
        if not self.cascade_table:
            return {}
        from .zen_engine import ZenWrapper
        full_context = dict(context or {})
        full_context["changed_param"] = changed_param
        raw = ZenWrapper.evaluate(
            self.cascade_table,
            full_context,
            env=self.env,
        )
        return self._normalize_cascade(raw)

    def _evaluate_availability(self, context):
        """Evaluate ``availability_table`` за дадения param context.

        :param context: dict от текущите param стойности (както са в
            configurator-а — design_params.<name> ключове).
        :returns: dict ``{param_name: {visible?, enabled?, allowed_values?,
            default_override?}}`` (само промените от default — UI взима
            default = visible+enabled).
        """
        self.ensure_one()
        if not self.availability_table:
            return {}
        from .zen_engine import ZenWrapper
        raw = ZenWrapper.evaluate(
            self.availability_table,
            context or {},
            env=self.env,
        )
        return self._normalize_availability(raw)
