# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""base_zen_decision pre-init: adopt zen.* metadata from mrp_design_matrix.

The ZEN kernel (zen.decision.table / zen.decision.log + their views, ACL,
fields, constraint, menus, actions) used to be owned by mrp_design_matrix.
On extraction the model NAMES are unchanged — only module ownership moves.
We reassign the existing ir_model_data rows BEFORE this module's models
and data load, so Odoo adopts the live tables/records instead of trying
to recreate them (and so mrp_design_matrix's update doesn't drop them as
orphans). Idempotent — a fresh install simply matches zero rows.
"""

import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    cr = env.cr
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'base_zen_decision'
         WHERE module = 'mrp_design_matrix'
           AND (
                name IN ('model_zen_decision_table', 'model_zen_decision_log')
             OR name LIKE 'field_zen_decision_%%'
             OR name LIKE 'access_zen_decision_%%'
             OR name LIKE 'constraint_zen_decision_%%'
             OR name LIKE 'action_zen_decision_%%'
             OR name LIKE 'view_zen_decision_%%'
             OR name LIKE 'menu_zen%%'
           )
    """)
    _logger.info(
        "base_zen_decision: adopted %s ir_model_data rows from "
        "mrp_design_matrix", cr.rowcount)
