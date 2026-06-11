# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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

        if isinstance(table_json, dict):
            content = json.dumps(table_json)
        else:
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

    @classmethod
    def evaluate(cls, table_json, context, env=None) -> dict:
        _logger.warning(
            "ZenWrapper is deprecated since 19.0.2.0.0 — use ZenRunner "
            "or env['zen.decision.table'].evaluate(code, context)."
        )
        return ZenRunner.evaluate(table_json, context, env=env)
