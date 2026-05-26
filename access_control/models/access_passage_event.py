# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.passage.event — append-only лог на всяко преминаване.

Един запис per evaluate() call (включително denied и violation cases).
Свързан със zen.decision.log за пълно audit trail.
"""

from odoo import fields, models


_RESULT = [
    ("accept", "Accepted"),
    ("deny", "Denied"),
    ("violation", "Violation"),
]


class AccessPassageEvent(models.Model):
    _name = "access.passage.event"
    _description = "Access Passage Event (append-only)"
    _order = "id desc"
    _rec_name = "id"

    control_point_id = fields.Many2one(
        "access.control.point", required=True, index=True,
        ondelete="restrict")
    credential_id = fields.Many2one(
        "access.credential", index=True, ondelete="set null")
    subject_id = fields.Many2one(
        related="credential_id.subject_id", store=True, index=True)
    perimeter_id = fields.Many2one(
        related="control_point_id.perimeter_id", store=True, index=True)
    ts = fields.Datetime(required=True, default=fields.Datetime.now,
                         index=True)
    direction = fields.Selection(
        [("in", "In"), ("out", "Out")],
        help="Derived от _derive_direction Python helper. None ако "
             "anomaly не позволява derive (forced/held/exit_without_entry).")
    anomaly_hint = fields.Char(
        help="Pattern detected от Python helper: forced / held / "
             "tailgating / exit_without_entry / denied_but_opened.")
    result = fields.Selection(_RESULT, required=True, index=True)
    signal_matrix = fields.Json(
        help="Raw signal matrix: {external_reader, internal_reader, "
             "magnet, door}. Pinned for forensic replay.")
    context_in = fields.Json(help="Context подадено на ZEN evaluate.")
    result_out = fields.Json(help="Резултат от ZEN.")
    zen_log_id = fields.Many2one(
        "zen.decision.log", ondelete="set null",
        help="Pointer към ZEN audit log row (full trace + table version).")
    company_id = fields.Many2one(
        related="control_point_id.company_id", store=True, index=True)
    violation_ids = fields.One2many("access.violation", "event_id")
    violation_count = fields.Integer(compute="_compute_violation_count")

    def _compute_violation_count(self):
        for rec in self:
            rec.violation_count = len(rec.violation_ids)

    def name_get(self):
        return [(
            r.id,
            "#%d %s @ %s %s%s" % (
                r.id, r.result.upper() if r.result else "?",
                r.control_point_id.name or "?",
                r.ts.strftime("%H:%M:%S") if r.ts else "—",
                " (%s)" % r.anomaly_hint if r.anomaly_hint else "",
            )
        ) for r in self]

    def action_open_direction_svg(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/access_control/svg/direction/{self.id}",
            "target": "new",
        }
