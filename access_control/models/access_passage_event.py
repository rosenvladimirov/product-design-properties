# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.passage.event — append-only лог на всяко преминаване.

Един запис per evaluate() call (включително denied и violation cases).
Свързан със zen.decision.log за пълно audit trail.
"""

from odoo import api, fields, models


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
    employee_id = fields.Many2one(
        "hr.employee",
        related="subject_id.employee_id", store=True, index=True,
        help="Employee derived from subject (for HR grouping in kanban/list).")
    perimeter_id = fields.Many2one(
        related="control_point_id.perimeter_id", store=True, index=True)
    controller_id = fields.Many2one(
        "access.controller",
        related="control_point_id.controller_id", store=True, index=True,
        help="Virtual ac (hardware wrapper) — which controller it came from.")
    ts = fields.Datetime(required=True, default=fields.Datetime.now,
                         index=True)
    time_slot_id = fields.Many2one(
        "access.time.slot",
        compute="_compute_time_slot", store=True, index=True,
        help="Site/door time slot active at event time "
             "(first match by sequence — night shift, entry window, etc.). "
             "For employee work hours see resource.calendar separately.")
    direction = fields.Selection(
        [("in", "In"), ("out", "Out")],
        help="Derived from _derive_direction Python helper. None when "
             "anomaly prevents derivation (forced/held/exit_without_entry).")
    anomaly_hint = fields.Char(
        help="Pattern detected by Python helper: forced / held / "
             "tailgating / exit_without_entry / denied_but_opened.")
    result = fields.Selection(_RESULT, required=True, index=True)
    signal_matrix = fields.Json(
        help="Raw signal matrix: {external_reader, internal_reader, "
             "magnet, door}. Pinned for forensic replay.")
    context_in = fields.Json(help="Context passed to ZEN evaluate.")
    result_out = fields.Json(help="Result from ZEN.")
    zen_log_id = fields.Many2one(
        "zen.decision.log", ondelete="set null",
        help="Pointer to ZEN audit log row (full trace + table version).")
    company_id = fields.Many2one(
        related="control_point_id.company_id", store=True, index=True)
    violation_ids = fields.One2many("access.violation", "event_id")
    violation_count = fields.Integer(compute="_compute_violation_count")

    def _compute_violation_count(self):
        for rec in self:
            rec.violation_count = len(rec.violation_ids)

    @api.depends("ts", "controller_id", "perimeter_id",
                 "credential_id", "credential_id.schedule_id")
    def _compute_time_slot(self):
        TimeSlot = self.env["access.time.slot"].sudo()
        for rec in self:
            if not rec.ts:
                rec.time_slot_id = False
                continue
            schedule = rec.credential_id.schedule_id \
                if rec.credential_id else False
            slots = TimeSlot.find_matching(
                rec.ts,
                controller=rec.controller_id or None,
                perimeter=rec.perimeter_id or None,
                schedule=schedule or None,
            )
            # First match by sequence (slots are sorted in search)
            rec.time_slot_id = slots[:1].id or False

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
