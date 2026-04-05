# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""
Post-migration script run when upgrading to 18.0.1.5.1.

Legacy installs may have BoMs with ``constraint_table`` (or other
matrix tables) but without the ``design_param_definition_id`` link on
the BoM — design parameter definitions were added in a later minor.
Without that link, the matrix engine cannot build a design context
and the MO confirmation fails at runtime.

This script scans for such BoMs and logs a warning for the operator
to review.  It does NOT auto-assign a definition (since choosing the
right one requires product-family knowledge), but it surfaces the
problem at upgrade time instead of at the first MO creation.

Lots are also inspected: any ``stock.lot`` whose
``design_param_definition_id`` is set but whose ``design_params`` is
empty gets a zero-ed Properties dict so subsequent reads do not crash.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(env, version):
    _check_boms_without_definition(env)
    _backfill_empty_design_params(env)
    _check_zen_engine(env)


def _check_boms_without_definition(env):
    Bom = env["mrp.bom"]
    # Any BoM with at least one matrix table set but no definition link.
    domain = [
        ("design_param_definition_id", "=", False),
        "|",
        "|",
        "|",
        ("constraint_table", "!=", False),
        ("geometry_table", "!=", False),
        ("material_table", "!=", False),
        ("operation_table", "!=", False),
    ]
    try:
        boms = Bom.search(domain)
    except Exception as e:
        _logger.warning(
            "MRP Design Matrix post-migration: BoM scan failed (%s) — skipping",
            e,
        )
        return
    if not boms:
        return
    _logger.warning(
        "MRP Design Matrix: %d BoM(s) have matrix tables but no "
        "design_param_definition_id — MO confirmation will fail "
        "until you link a definition. Affected BoMs: %s",
        len(boms),
        boms.ids,
    )


def _backfill_empty_design_params(env):
    Lot = env["stock.lot"]
    try:
        lots = Lot.search(
            [
                ("design_param_definition_id", "!=", False),
                ("design_params", "=", False),
            ]
        )
    except Exception as e:
        _logger.warning(
            "MRP Design Matrix post-migration: lot scan failed (%s) — skipping",
            e,
        )
        return
    if not lots:
        return
    _logger.info(
        "MRP Design Matrix: back-filling empty design_params on %d lot(s)",
        len(lots),
    )
    try:
        lots.write({"design_params": {}})
    except Exception as e:
        _logger.warning(
            "MRP Design Matrix post-migration: design_params backfill failed "
            "(%s) — leaving lots untouched",
            e,
        )


def _check_zen_engine(env):
    """Emit a loud warning if zen-engine is missing at upgrade time."""
    try:
        import zen  # noqa: F401
    except ImportError:
        _logger.warning(
            "MRP Design Matrix upgraded but zen-engine is not installed. "
            "Run `pip install zen-engine` in the Odoo environment, or set "
            "the system parameter 'mrp_design_matrix.allow_missing_zen_engine' "
            "to '1' to enable the soft fallback (matrix evaluation becomes "
            "a no-op — use only for staged rollouts)."
        )
