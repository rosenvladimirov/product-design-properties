# Copyright 2026 BL Consulting
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
"""

import json
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import zen

    _ZEN_AVAILABLE = True
except ImportError:
    _ZEN_AVAILABLE = False
    _logger.warning(
        "zen-engine not installed. MRP Design Matrix will not work. "
        "Run: pip install zen-engine"
    )


class ZenWrapper:
    """Stateless GoRules evaluator — creates a decision per call."""

    _engine = None

    @classmethod
    def _get_engine(cls):
        if not _ZEN_AVAILABLE:
            raise UserError(
                "zen-engine Python package is not installed.\n"
                "Install it with:  pip install zen-engine"
            )
        if cls._engine is None:
            cls._engine = zen.ZenEngine()
        return cls._engine

    @classmethod
    def evaluate(cls, table_json, context: dict) -> dict:
        """
        Evaluate a GoRules decision table against *context*.

        :param table_json: JSONB value from an ``mrp.bom`` field
                           (dict or JSON string).
        :param context:    Flat dict of design parameters.
        :returns:          Result dict from GoRules (structure depends on
                           the table's hit policy and output columns).
        :raises UserError: If the engine is unavailable or evaluation fails.
        """
        if not table_json:
            return {}

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
            raise UserError(f"Design matrix evaluation error: {e}") from e
