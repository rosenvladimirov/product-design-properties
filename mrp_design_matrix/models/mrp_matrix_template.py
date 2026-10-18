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
import json
import logging

from odoo import _, api, fields, models
from odoo.addons.base_zen_decision.models.zen_engine import (
    ZenRunner,
    normalize_jdm_graph,
    validate_graph,
)
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Легаси и модерни типове на таблицата — при сканиране на T2 приемаме и двата.
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

    Незадължителните слоеве на конфигуратора (порт от 18.0, фазите A–E):
        - availability_table : TΠ — видимост/достъпност/позволени стойности
        - cascade_table      : TΦ — каскада на стойности (+ derive_expression)
        - lookup_tables      : именувани таблици за ``lookup()`` в TΦ
        - multiplicity_table : TΩ — метаданни за многоинстанционни изделия
        - layout_table       : TΛ — UX подсказки по параметър
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

    _RULE_TABLE_FIELDS = ("constraint_table", "geometry_table",
                          "material_table", "operation_table")
    # Слоевете на конфигуратора (фазите A–E от 18.0) се нормализират при
    # запис като T0–T3, но НЕ минават през _check_rule_tables: данните от
    # прода на 18 влизат с ETL и стар плосък/непълен граф не бива да спира
    # вноса. Двигателят нормализира и при оценка.
    _CONFIGURATOR_TABLE_FIELDS = ("availability_table", "cascade_table",
                                  "multiplicity_table", "layout_table")

    @api.model
    def _pop_industry_tag(self, vals):
        """Translate a string ``industry`` key in *vals* to ``industry_id``."""
        if "industry" in vals and not isinstance(vals.get("industry"), int):
            tag = vals.pop("industry")
            industry = self.env["design.industry"].sudo()._resolve(tag)
            vals["industry_id"] = industry.id or False
        return vals

    @api.model
    def _normalize_rule_tables(self, vals):
        """Zero-churn нормализация (D2): заварените data файлове подават
        „плосък" формат ({'nodes':[{type:'decisionTable'}]}, без edges) —
        zen-engine го приема МЪЛЧАЛИВО и връща [] за всеки контекст
        (T3=[] инцидентът). Опаковаме го в пълен JDM граф при запис;
        data файловете остават непокътнати (както industry tag-а)."""
        for fname in self._RULE_TABLE_FIELDS + self._CONFIGURATOR_TABLE_FIELDS:
            if vals.get(fname):
                vals[fname] = normalize_jdm_graph(vals[fname])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_industry_tag(vals)
            self._normalize_rule_tables(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._pop_industry_tag(vals)
        self._normalize_rule_tables(vals)
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
            "GoRules JDM JSON: reactive value propagation. When parameter X "
            "changes, a value is derived for parameter Y. Outputs per rule: "
            "target_param, copy_from (the parameter whose value is copied), "
            "derive_value (an explicit value), derive_expression (an "
            "expression over the current parameters with the lookup() "
            "helper), only_if_empty (do not overwrite an explicit choice). "
            "Evaluated by the design configurator on every parameter change. "
            "Optional layer."
        ),
    )
    layout_table = fields.Json(
        "TΛ — Layout / UX Hints",
        help=(
            "GoRules JDM JSON: declarative UX rules per parameter. Outputs per "
            "rule: param, section, widget_hint (segment/spinner/slider/"
            "color_picker), customer_visible (customer-pickable or internal), "
            "submodal (sub-dialog id), order. Evaluated once when the "
            "configurator loads. Optional layer."
        ),
    )
    multiplicity_table = fields.Json(
        "TΩ — Multiplicity",
        help=(
            "GoRules JDM JSON: metadata for multi-instance products (several "
            "shutters, doors or shelves in one item). Outputs: count_param "
            "(the parameter that holds N), per_instance_params (the parameters "
            "that differ per instance, e.g. [\"width\", \"height\"]), "
            "aggregator (sum/list/concat), skip_when. Consumers loop over the "
            "lot's Multi-Instance Data. Optional layer."
        ),
    )
    lookup_tables = fields.Json(
        "Lookup Tables",
        help=(
            "Named lookup tables for TΦ derive_expression rules through "
            "lookup(name, key1, key2, ...). Structure: "
            "{table: {key1: {key2: [[threshold, result], ...]}}}. A list as "
            "the last level is matched by ordered numeric threshold (the first "
            "threshold >= the input); a dict is matched by key. Optional."
        ),
    )
    availability_table = fields.Json(
        "TΠ — Param Availability",
        help=(
            "GoRules JDM JSON: reactive UI control for the design configurator. "
            "Inputs are the current parameters; outputs per rule: param, "
            "visible, enabled, allowed_values, default_override. Evaluated on "
            "every parameter change. Optional layer: when empty the "
            "configurator behaves as before."
        ),
    )

    @api.constrains("constraint_table", "geometry_table",
                    "material_table", "operation_table")
    def _check_rule_tables(self):
        """Write-time валидация на шаблонните T0-T3 графи (D2) — както на
        BoM-а: счупен граф не бива да влиза тихо и после да се копира в
        десетки BoM-ове през action_load_from_template."""
        labels = {
            "constraint_table": "T0 (Constraints)",
            "geometry_table": "T1 (Geometry)",
            "material_table": "T2 (Materials)",
            "operation_table": "T3 (Operations)",
        }
        for rec in self:
            problems = []
            for fname, label in labels.items():
                # валидира се НОРМАЛИЗИРАНАТА стойност: заварен плосък
                # формат е ЛЕЧИМ (migration/write hook го опакова) и не бива
                # да блокира write на съседно поле на жива база.
                problems += ["%s: %s" % (label, e)
                             for e in validate_graph(
                                 normalize_jdm_graph(rec[fname]))]
            if problems:
                raise ValidationError(
                    _("Invalid rule table on template %(tmpl)s:\n- %(problems)s",
                      tmpl=rec.display_name,
                      problems="\n- ".join(problems)))

    # ── T2: обявените ключове на коефициентите ─────────────────────────────
    # T2 издава стойности ``bom_line_coeff_key``, които редовете на рецептата
    # трябва да декларират в ``matrix_coeff_rule``, за да получат коефициент.
    # Оттук mrp.bom._check_t2_wiring сравнява обявеното с декларираното.

    @staticmethod
    def _extract_t2_coeff_keys(table_json):
        """Множеството различни ``bom_line_coeff_key`` от T2 таблица (dict).

        JDM пази низовите литерали в кавички (``'"motor-o"'`` → ``motor-o``).
        Празни стойности и стойности, които не са низ, се пропускат; приемат се и двата типа
        на таблицата (легаси ``decisionTable`` и ``decisionTableNode``).
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
        """Обвивка за конкретен шаблон."""
        self.ensure_one()
        return self._extract_t2_coeff_keys(self.material_table)

    # ── TΠ — достъпност на параметрите ────────────────────────────────────
    # Реактивен слой: при всяка промяна конфигураторът праща контекста и
    # получава по параметър visible / enabled / allowed_values /
    # default_override. Обикновено hitPolicy=collect — правилата се сливат.

    _AVAILABILITY_KEYS = ("visible", "enabled", "allowed_values", "default_override")

    @classmethod
    def _normalize_availability(cls, raw_payload):
        """Суровия изход на двигателя → ``{param: {visible, enabled,
        allowed_values, default_override}}``.

        Приема списък (collect), единично правило (dict) или dict с ключ
        ``result``. ``visible``/``enabled`` се натрупват с И (False печели),
        ``allowed_values`` се пресичат, ``default_override`` — последното
        правило печели.
        """
        items = []
        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            if "result" in raw_payload and isinstance(raw_payload["result"], list):
                items = raw_payload["result"]
            elif "param" in raw_payload:
                items = [raw_payload]
            else:
                # двигателят може да върне направо речник по параметър
                return {k: v for k, v in raw_payload.items() if isinstance(v, dict)}
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
                    if isinstance(value, list):
                        if isinstance(state.get("allowed_values"), list):
                            state["allowed_values"] = [
                                v for v in state["allowed_values"] if v in value
                            ]
                        else:
                            state["allowed_values"] = list(value)
                elif key in ("visible", "enabled"):
                    if key in state:
                        state[key] = bool(state[key]) and bool(value)
                    else:
                        state[key] = bool(value)
                else:
                    state[key] = value
        return out

    # ── TΦ — каскада на стойностите ───────────────────────────────────────
    # Когато параметър X се промени, правилото дава стойност на Y: копие от
    # друг параметър, изрична стойност или израз (derive_expression) върху
    # текущите стойности с помощника lookup().

    _CASCADE_KEYS = ("copy_from", "derive_value", "derive_expression", "only_if_empty")

    @staticmethod
    def _make_lookup(lookup_tables):
        """Помощникът ``lookup(name, *keys)`` за израза на TΦ.

        Междинните ключове се търсят като низ. На последното ниво списък от
        двойки ``[праг, резултат]`` се търси по подреден праг (първият праг
        >= входа — например кутия по височина), а речник — по ключ. Липсващ
        път връща None.
        """
        tables = lookup_tables or {}

        def lookup(name, *keys):
            cur = tables.get(name)
            if cur is None or not keys:
                return None
            for k in keys[:-1]:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(str(k))
                if cur is None:
                    return None
            last = keys[-1]
            if isinstance(cur, list):
                try:
                    last_num = float(last)
                except (TypeError, ValueError):
                    return None
                for entry in cur:
                    if isinstance(entry, (list, tuple)) and len(entry) == 2:
                        try:
                            if float(entry[0]) >= last_num:
                                return entry[1]
                        except (TypeError, ValueError):
                            continue
                return None
            if isinstance(cur, dict):
                return cur.get(str(last))
            return None

        return lookup

    @classmethod
    def _normalize_cascade(cls, raw_payload):
        """Суровия изход → ``{target_param: {copy_from?, derive_value?,
        derive_expression?, only_if_empty?}}``; при няколко правила за една
        цел печели последното (редът в JDM е каноничен)."""
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

    @api.model
    def _resolve_cascade_expressions(self, normalized, context, lookup_tables):
        """Замества ``derive_expression`` с изчисления ``derive_value``.

        Пространството е текущият контекст плюс lookup() и основните
        математически функции. Грешен израз се записва в лога и се
        пропуска — не събаря конфигуратора. Изричен ``derive_value``
        печели пред израза (както в 18.0).
        """
        helpers = {
            "lookup": self._make_lookup(lookup_tables or {}),
            "min": min, "max": max, "abs": abs,
            "int": int, "float": float, "str": str,
            "round": round, "len": len,
        }
        for target, spec in normalized.items():
            if not isinstance(spec, dict) or not spec.get("derive_expression"):
                continue
            expr = spec.pop("derive_expression")
            eval_ctx = {**(context or {}), **helpers}
            try:
                value = safe_eval(expr, eval_ctx)
            except Exception as exc:  # noqa: BLE001 — грешен израз не бива да чупи UI
                _logger.warning(
                    "TΦ derive_expression failed for target=%s expr=%r: %s",
                    target, expr, exc,
                )
                continue
            if value is not None and "derive_value" not in spec:
                spec["derive_value"] = value
        return normalized

    def _evaluate_cascade(self, changed_param, context):
        """Оценява ``cascade_table`` за промяна на ``changed_param``.

        :param changed_param: етикетът на параметъра (``string`` от
            дефиницията), който се промени.
        :param context: текущите стойности на параметрите.
        :returns: ``{target_param: {copy_from?, derive_value?, only_if_empty?}}``;
            ``derive_expression`` вече е изчислен в ``derive_value``.
        """
        self.ensure_one()
        if not self.cascade_table:
            return {}
        full_context = dict(context or {})
        full_context["changed_param"] = changed_param
        raw = ZenRunner.evaluate(self.cascade_table, full_context, env=self.env)
        normalized = self._normalize_cascade(raw)
        return self._resolve_cascade_expressions(
            normalized, full_context, self.lookup_tables)

    # ── TΩ — многоинстанционни изделия ────────────────────────────────────

    _MULTIPLICITY_KEYS = ("count_param", "per_instance_params", "aggregator", "skip_when")

    @classmethod
    def _normalize_multiplicity(cls, raw_payload):
        """Суровия изход → един речник с метаданни (първото съвпадение)."""
        items = []
        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            if "result" in raw_payload and isinstance(raw_payload["result"], list):
                items = raw_payload["result"]
            elif "count_param" in raw_payload:
                items = [raw_payload]
        if not items or not isinstance(items[0], dict):
            return {}
        first = items[0]
        return {
            key: first[key] for key in cls._MULTIPLICITY_KEYS
            if key in first and first[key] not in (None, "", False)
        }

    def _evaluate_multiplicity(self, context):
        """Оценява ``multiplicity_table`` за контекста; празно без TΩ."""
        self.ensure_one()
        if not self.multiplicity_table:
            return {}
        raw = ZenRunner.evaluate(self.multiplicity_table, context or {}, env=self.env)
        return self._normalize_multiplicity(raw)

    # ── TΛ — UX подсказки ─────────────────────────────────────────────────

    _LAYOUT_KEYS = ("section", "widget_hint", "customer_visible", "submodal", "order")

    @classmethod
    def _normalize_layout(cls, raw_payload):
        """Суровия изход → ``{param: {section?, widget_hint?,
        customer_visible?, submodal?, order?}}``; последното правило печели
        за всяка клетка."""
        items = []
        if isinstance(raw_payload, list):
            items = raw_payload
        elif isinstance(raw_payload, dict):
            if "result" in raw_payload and isinstance(raw_payload["result"], list):
                items = raw_payload["result"]
            elif "param" in raw_payload:
                items = [raw_payload]
        out = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            param = item.get("param")
            if not param:
                continue
            spec = out.setdefault(param, {})
            for key in cls._LAYOUT_KEYS:
                if key not in item:
                    continue
                value = item[key]
                if key == "customer_visible":
                    spec[key] = bool(value)
                elif value not in (None, "", False):
                    spec[key] = value
        return out

    def _evaluate_layout(self, context=None):
        """Оценява ``layout_table``; празно без TΛ."""
        self.ensure_one()
        if not self.layout_table:
            return {}
        raw = ZenRunner.evaluate(self.layout_table, context or {}, env=self.env)
        return self._normalize_layout(raw)

    def _evaluate_availability(self, context):
        """Оценява ``availability_table``; връща само отклоненията от
        подразбирането (видим и достъпен)."""
        self.ensure_one()
        if not self.availability_table:
            return {}
        raw = ZenRunner.evaluate(self.availability_table, context or {}, env=self.env)
        return self._normalize_availability(raw)
