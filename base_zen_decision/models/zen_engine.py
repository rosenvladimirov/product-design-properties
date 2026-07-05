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
"""
Thin wrapper around the ``zen-engine`` (GoRules) Python library.

Usage::

    from odoo.addons.mrp_design_matrix.models.zen_engine import ZenWrapper

    result = ZenWrapper.evaluate(bom.constraint_table, design_context)
    errors   = result.get("errors", [])
    warnings = result.get("warnings", [])

The JSON stored in ``mrp.bom`` fields is the GoRules JDM format.
See https://gorules.io/docs/ for the full specification.

Install notes
-------------

``zen-engine`` is an external Python dependency declared in the module
manifest.  If it is missing at runtime the wrapper raises a clear
``UserError`` pointing the operator at ``pip install zen-engine``.

Administrators who want to install the module before the engine is
available (e.g. staged rollouts) can set the system parameter
``mrp_design_matrix.allow_missing_zen_engine`` to ``1`` — the wrapper
will then become a no-op and return ``{}`` for every call, which
effectively disables the matrix engine without breaking MO creation
for BoMs that do not use matrix tables.

**Warning:** with the fallback enabled, T0 constraints are NOT
enforced.  Use it only while the host is being prepared, and never
in production.
"""

import json
import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import zen

    _ZEN_AVAILABLE = True
except ImportError:
    _ZEN_AVAILABLE = False
    _logger.warning(
        "zen-engine not installed. MRP Design Matrix evaluation will raise "
        "until the package is available. Run: pip install zen-engine"
    )


_ALLOW_MISSING_PARAM = "mrp_design_matrix.allow_missing_zen_engine"


def normalize_jdm_graph(graph):
    """Нормализира ЛЕГАСИ „плосък" формат към пълен JDM граф.

    Заварените шаблони (напр. solid_door matrix_templates.xml) са
    ``{'nodes': [{'type': 'decisionTable', ...}]}`` — БЕЗ edges и БЕЗ
    input/output nodes. zen-engine ПРИЕМА такъв граф мълчаливо и връща []
    за всеки контекст (коренът на T3=[] инцидента на прод). Опаковаме:
    decisionTable → decisionTableNode + inputNode/outputNode + 2 edges;
    rules получават '_id', inputs/outputs получават 'field' (= name), ако
    липсват. Валиден пълен граф се връща непроменен (идемпотентно).
    Data файловете остават непокътнати — zero-churn (както industry tag).
    """
    if not graph or not isinstance(graph, dict):
        return graph
    nodes = graph.get("nodes") or []
    if graph.get("edges"):
        return graph  # вече е пълен граф
    if len(nodes) != 1 or nodes[0].get("type") not in (
            "decisionTable", "decisionTableNode"):
        return graph  # непознат формат — не гадаем (валидаторът ще каже)
    dt = dict(nodes[0])
    dt["type"] = "decisionTableNode"
    content = dict(dt.get("content") or {})
    for key in ("inputs", "outputs"):
        cols = []
        for col in content.get(key) or []:
            col = dict(col)
            if not col.get("field"):
                col["field"] = col.get("name") or col.get("id")
            cols.append(col)
        content[key] = cols
    rules = []
    for i, rule in enumerate(content.get("rules") or [], start=1):
        rule = dict(rule)
        rule.setdefault("_id", "r%d" % i)
        rules.append(rule)
    content["rules"] = rules
    dt["content"] = content
    nid = dt.get("id") or "table"
    node_in = {"id": "%s-in" % nid, "type": "inputNode", "name": "Request"}
    node_out = {"id": "%s-out" % nid, "type": "outputNode", "name": "Response"}
    return {
        "nodes": [node_in, dt, node_out],
        "edges": [
            {"id": "%s-e1" % nid, "sourceId": node_in["id"],
             "targetId": nid},
            {"id": "%s-e2" % nid, "sourceId": nid,
             "targetId": node_out["id"]},
        ],
    }


def validate_graph(graph):
    """Структурна валидация на GoRules JDM граф. Връща списък от грешки
    (празен списък = валиден). НЕ изисква zen-engine (чиста структура).

    Хваща класа „счупен граф" дефекти (T3=[] инцидентът на прод: таблица,
    която тихо връща празно за всеки контекст): edge към несъществуващ
    node, откачен decision table (без входящ/изходящ edge), липсващ
    input/output node, decision table без rules/inputs/outputs.
    """
    errs = []
    if not graph:
        return errs  # празно поле е легитимно (таблицата е опционална)
    if isinstance(graph, str):
        try:
            graph = json.loads(graph)
        except (TypeError, ValueError):
            return ["not valid JSON"]
    if not isinstance(graph, dict):
        return ["graph must be a JSON object"]
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return ["graph has no nodes"]
    if not isinstance(edges, list):
        # не връщаме рано: съберѝ ПЪЛНАТА диагностика (липсващи input/output
        # nodes и т.н.) — по-полезно съобщение за оператора
        errs.append("graph has no edges list")
        edges = []
    ids = set()
    types = {}
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            errs.append("node without id")
            continue
        if n["id"] in ids:
            errs.append("duplicate node id %r" % n["id"])
        ids.add(n["id"])
        types[n["id"]] = n.get("type") or ""
    type_vals = list(types.values())
    if "inputNode" not in type_vals:
        errs.append("missing inputNode")
    if "outputNode" not in type_vals:
        errs.append("missing outputNode")
    has_in = set()
    has_out = set()
    for e in edges:
        src, tgt = (e or {}).get("sourceId"), (e or {}).get("targetId")
        if src not in ids:
            errs.append("edge sourceId %r references missing node" % src)
        if tgt not in ids:
            errs.append("edge targetId %r references missing node" % tgt)
        has_out.add(src)
        has_in.add(tgt)
    for nid, ntype in types.items():
        if ntype == "decisionTableNode":
            if nid not in has_in or nid not in has_out:
                errs.append(
                    "decision table %r is disconnected (needs incoming "
                    "and outgoing edges)" % nid)
            content = next(
                (n.get("content") for n in nodes if n.get("id") == nid), None)
            if not isinstance(content, dict):
                errs.append("decision table %r has no content" % nid)
                continue
            # празна таблица (0 rules) НЕ е тиха отрова — потребителят я
            # вижда празна (UI "Create Table" започва от нула). Блокираме
            # само СТРУКТУРНО счупени: rules има, а inputs/outputs липсват.
            rules = content.get("rules")
            if not isinstance(rules, list):
                errs.append("decision table %r has no rules list" % nid)
            elif rules:
                for key in ("inputs", "outputs"):
                    val = content.get(key)
                    if not isinstance(val, list) or not val:
                        errs.append(
                            "decision table %r has rules but empty/missing %r"
                            % (nid, key))
        elif ntype == "inputNode" and nid not in has_out:
            errs.append("inputNode %r has no outgoing edge" % nid)
        elif ntype == "outputNode" and nid not in has_in:
            errs.append("outputNode %r has no incoming edge" % nid)
    # Семантична проверка: ако zen-engine е наличен, компилирай (бързо,
    # без evaluate) — хваща грешки, които структурната проверка не вижда.
    if not errs and _ZEN_AVAILABLE:
        try:
            zen.ZenEngine().create_decision(json.dumps(graph))
        except Exception as exc:  # noqa: BLE001
            errs.append("zen-engine rejects the graph: %s" % exc)
    return errs


def _soft_fallback_enabled(env) -> bool:
    """Return True when the sysadmin allowed running without zen-engine."""
    try:
        value = env["ir.config_parameter"].sudo().get_param(_ALLOW_MISSING_PARAM, "")
    except Exception:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class ZenRunner:
    """Stateless GoRules evaluator — creates a decision per call.

    Renamed from ZenWrapper in 19.0.2.0.0 (kernel extraction). The
    ZenWrapper name remains as an alias for back-compat (виж края на файла).
    Future split: този клас се мести в нов модул `base_zen_decision`.
    """

    _engine = None

    @classmethod
    def is_available(cls) -> bool:
        return _ZEN_AVAILABLE

    @classmethod
    def _get_engine(cls):
        if not _ZEN_AVAILABLE:
            raise UserError(
                _(
                    "zen-engine Python package is not installed.\n"
                    "Install it with:  pip install zen-engine\n\n"
                    "For staged rollouts you can temporarily set the system "
                    "parameter 'mrp_design_matrix.allow_missing_zen_engine' "
                    "to '1' — this disables the matrix engine but allows "
                    "MOs to be created for BoMs without matrix tables."
                )
            )
        if cls._engine is None:
            cls._engine = zen.ZenEngine()
        return cls._engine

    @classmethod
    def evaluate(cls, table_json, context: dict, env=None) -> dict:
        """
        Evaluate a GoRules decision table against *context*.

        :param table_json: JSONB value from an ``mrp.bom`` field
                           (dict or JSON string).
        :param context:    Flat dict of design parameters.
        :param env:        Optional Odoo environment used to read the
                           ``allow_missing_zen_engine`` soft-fallback
                           system parameter.  If ``zen-engine`` is
                           missing and the flag is on, the call logs a
                           warning and returns ``{}``.
        :returns:          Result dict from GoRules (structure depends on
                           the table's hit policy and output columns).
        :raises UserError: If the engine is unavailable and the soft
                           fallback is disabled, or if evaluation fails.
        """
        if not table_json:
            return {}

        if not _ZEN_AVAILABLE:
            if env is not None and _soft_fallback_enabled(env):
                _logger.warning(
                    "zen-engine missing — matrix evaluation skipped "
                    "(soft fallback enabled via system parameter)"
                )
                return {}
            # Raise the detailed error
            cls._get_engine()  # will raise UserError

        engine = cls._get_engine()

        # Защитна нормализация: легаси „плосък" JDM (type=decisionTable, без
        # edges/input/output nodes) се среща в стари бази и директни викания —
        # zen-engine 0.53 го отхвърля с Invalid JSON. Идемпотентно за пълни графи.
        if isinstance(table_json, dict):
            content = json.dumps(normalize_jdm_graph(table_json))
        else:
            try:
                content = json.dumps(normalize_jdm_graph(json.loads(table_json)))
            except (ValueError, TypeError):
                content = table_json

        try:
            decision = engine.create_decision(content)
            result = decision.evaluate(context)
            return result.get("result", result)
        except Exception as e:
            _logger.error("GoRules evaluation error: %s", e)
            raise UserError(_("Design matrix evaluation error: %s") % e) from e


# ── Back-compat alias ───────────────────────────────────────────────
# Преименувахме ZenWrapper → ZenRunner в 19.0.2.0.0 (kernel extraction).
# Стара публичност на ZenWrapper се запазва за един релийз цикъл — после
# се премахва когато всички консуматори ползват `env['zen.decision.table']`.
class ZenWrapper(ZenRunner):
    """DEPRECATED: use ZenRunner или
    env['zen.decision.table'].evaluate(code, context). Този alias ще
    отпадне в 19.0.3.0.0."""

    _deprecation_logged = False

    @classmethod
    def evaluate(cls, table_json, context, env=None) -> dict:
        # log-once: warning-ът на ВСЯКА евалуация спамеше hot-path лога
        # (по 4 T0-T3 виквания на MO/cost симулация).
        if not ZenWrapper._deprecation_logged:
            ZenWrapper._deprecation_logged = True
            _logger.warning(
                "ZenWrapper is deprecated since 19.0.2.0.0 — use ZenRunner "
                "or env['zen.decision.table'].evaluate(code, context)."
            )
        return ZenRunner.evaluate(table_json, context, env=env)
