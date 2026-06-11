# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""ZEN decision table — versioned GoRules graph storage + evaluate API.

Generic kernel модел — НЯМА mrp-специфично знание. Първоначално живее в
mrp_design_matrix; при бъдещ split се мести в `base_zen_decision`.

Един `code` може да има много `version` записи (история), но само един
с `active=True` за дадена (code, company_id) комбинация — record rule
гарантира изолация per company (виж Open Q#2 от плана).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .zen_engine import ZenRunner

_logger = logging.getLogger(__name__)


class ZenDecisionTable(models.Model):
    _name = "zen.decision.table"
    _description = "ZEN Decision Table (versioned graph)"
    _order = "domain, code, version desc"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Programmatic key. Resolution: latest active version per "
             "(code, company_id). E.g. 'mrp_t0_width_check', "
             "'access_default_a2_perimeter'.")
    domain = fields.Char(
        required=True, index=True,
        help="Group label: 'mrp_matrix', 'access', 'gfo', etc. Used "
             "for UI filtering + bulk export of all graphs for one domain.")
    graph = fields.Json(
        required=True,
        help="GoRules JDM document (nodes + edges). Stored as JSONB.")
    version = fields.Integer(
        required=True, default=1, readonly=True,
        help="Monotonically increasing. publish_new_version() creates a "
             "new row with version+1, archives the previous.")
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
        help="NULL = global graph (rare; reserved for system defaults).")
    active = fields.Boolean(default=True)
    notes = fields.Text(help="Free-text changelog за тази версия.")

    _sql_constraints = [
        (
            "code_version_company_uniq",
            "unique(code, version, company_id)",
            "Each (code, version) must be unique per company.",
        ),
    ]

    # ── Lookup helpers ─────────────────────────────────────────────────
    @api.model
    def get_active(self, code, company_id=None):
        """Return the active record for `code` in the given company (or
        the current env company). Raises ValidationError if none."""
        company_id = company_id or self.env.company.id
        rec = self.search([
            ("code", "=", code),
            ("active", "=", True),
            ("company_id", "in", [company_id, False]),
        ], order="company_id desc, version desc", limit=1)
        if not rec:
            raise ValidationError(
                _("No active ZEN decision table for code=%(code)s in "
                  "company=%(cid)s.",
                  code=code, cid=company_id))
        return rec

    # ── Public API ────────────────────────────────────────────────────
    def evaluate(self, context, trace=False):
        """Pure evaluation — no side effects. Caller logs via .log() if
        needed.

        :param context: flat dict — input to the JDM graph
        :param trace:   include ZEN trace for debugging (placeholder —
                        current zen-engine binding doesn't expose trace;
                        kept in signature for future when it does)
        :returns:       {"result": dict, "trace": dict|None,
                         "version": int, "table_id": int}
        """
        self.ensure_one()
        result = ZenRunner.evaluate(self.graph, context, env=self.env)
        return {
            "result": result,
            "trace": None,  # TODO: ZEN engine trace API когато стане налично
            "version": self.version,
            "table_id": self.id,
        }

    def log(self, context, result, trace=None, executed_in="odoo"):
        """Create an audit log entry. Separate call so caller controls
        what gets logged (e.g. sample 1-in-N for high-volume callers)."""
        self.ensure_one()
        return self.env["zen.decision.log"].sudo().create({
            "table_id": self.id,
            "table_version": self.version,
            "context_in": context,
            "result_out": result,
            "trace": trace,
            "executed_in": executed_in,
        })

    def publish_new_version(self, new_graph, notes=None):
        """Atomic — archives self, creates new record with version+1.
        Returns the new record."""
        self.ensure_one()
        new_rec = self.copy({
            "graph": new_graph,
            "version": self.version + 1,
            "active": True,
            "notes": notes or False,
        })
        self.with_context(_skip_active_guard=True).write({"active": False})
        return new_rec

    @api.constrains("active", "code", "company_id")
    def _check_single_active_per_code_company(self):
        if self.env.context.get("_skip_active_guard"):
            return
        for rec in self.filtered("active"):
            others = self.search([
                ("code", "=", rec.code),
                ("company_id", "=", rec.company_id.id),
                ("active", "=", True),
                ("id", "!=", rec.id),
            ])
            if others:
                raise ValidationError(
                    _("Only one active ZEN table is allowed per "
                      "(code='%(code)s', company='%(co)s'). "
                      "Use publish_new_version() to roll forward.",
                      code=rec.code, co=rec.company_id.display_name))

    # ── Sync контракт към proxy (Phase 1 = Odoo-side ready;
    # ── proxy consumption = Phase 3) ─────────────────────────────────
    def _build_sync_payload(self):
        """Returns a dict the proxy can apply locally. Caller signs with
        proxy.registry_secret HMAC before POSTing."""
        self.ensure_one()
        return {
            "code": self.code,
            "domain": self.domain,
            "version": self.version,
            "graph": self.graph,
            "company_id": self.company_id.id,
        }

    def action_push_to_proxies(self):
        """UI button — pushes this graph to all active proxies that
        declared support for the `domain` of this table. Skipped if
        erpnet.fp.proxy is not installed (mrp_design_matrix doesn't
        depend on Fleet — graceful no-op)."""
        self.ensure_one()
        Proxy = self.env.get("erpnet.fp.proxy")
        if Proxy is None:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": _("erpnet.fp.proxy not installed — "
                                  "graph push skipped."),
                },
            }
        payload = self._build_sync_payload()
        pushed = 0
        for proxy in Proxy.sudo().search([("state", "=", "active")]):
            if hasattr(proxy, "_push_zen_graph"):
                try:
                    proxy._push_zen_graph(payload)
                    pushed += 1
                except Exception as e:  # noqa: BLE001
                    _logger.warning(
                        "ZEN graph push to %s failed: %s", proxy.name, e)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if pushed else "warning",
                "message": _("ZEN graph pushed to %d proxies.") % pushed,
            },
        }
