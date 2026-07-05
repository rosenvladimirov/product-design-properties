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
"""ZEN decision audit log — append-only.

Records every evaluate() call for forensic + debug purposes. Important
for offline access decisions ("коя графа отвори вратата в 03:14") —
table_version snapshots the version that was active at decision time
even if a newer version has since been published.

Generic kernel модел — без mrp-домейн знание. При бъдещ split се мести
в `base_zen_decision`.
"""

from odoo import api, fields, models


class ZenDecisionLog(models.Model):
    _name = "zen.decision.log"
    _description = "ZEN Decision audit log (append-only)"
    _order = "id desc"
    _rec_name = "id"

    table_id = fields.Many2one(
        "zen.decision.table", required=True, index=True,
        ondelete="restrict")
    table_version = fields.Integer(
        required=True,
        help="Snapshot of table.version at decision time. May differ "
             "from current table.version if newer versions exist.")
    table_code = fields.Char(
        related="table_id.code", store=True, index=True,
        help="Cached for filtered queries без JOIN.")
    table_domain = fields.Char(related="table_id.domain", store=True)
    context_in = fields.Json(required=True)
    result_out = fields.Json(required=True)
    trace = fields.Json(
        help="ZEN engine trace (когато engine API стане налично — "
             "currently always None в Phase 1).")
    executed_in = fields.Selection(
        [("odoo", "Odoo"), ("controller", "Controller (offline)")],
        required=True, default="odoo", index=True,
        help="Where the decision physically ran. 'controller' rows "
             "arrive via proxy drain on reconnect.")
    company_id = fields.Many2one(
        related="table_id.company_id", store=True, index=True)
    create_date = fields.Datetime(readonly=True, index=True)

    # NO write/unlink overrides — append-only enforced via ACL
    # (ir.model.access.csv: create=1, write=0, unlink=0 за group_user;
    # admin може unlink за GDPR purge).

    @api.depends("table_code", "table_version", "executed_in", "create_date")
    def _compute_display_name(self):
        # Compact: "#42 mrp_t0_constraints@v3 [odoo] 2026-05-26 14:33"
        # (беше name_get() — премахнат в Odoo 17 → мъртъв код; display_name
        # падаше до суровото id.)
        for r in self:
            r.display_name = "#%d %s@v%d [%s] %s" % (
                r.id, r.table_code or "?", r.table_version or 0,
                r.executed_in or "?",
                (r.create_date.strftime("%Y-%m-%d %H:%M")
                 if r.create_date else "—"),
            )
