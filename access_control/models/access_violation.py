# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.violation — incident запис със HR review queue."""

from odoo import _, fields, models


_VIOLATION_TYPE = [
    ("forced", "Forced (magnet break w/o reader)"),
    ("held", "Door held open (timeout)"),
    ("denied_but_opened", "Denied but opened"),
    ("exit_without_entry", "Exit without entry"),
    ("tailgating", "Tailgating (multiple passes <3s)"),
    ("other", "Other"),
]
_PRIORITY = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]
_HR_REVIEW = [
    ("none", "No review needed"),
    ("pending", "Pending review"),
    ("reviewed", "Reviewed (cleared)"),
    ("dismissed", "Dismissed"),
]


class AccessViolation(models.Model):
    _name = "access.violation"
    _description = "Access Violation"
    _order = "id desc"
    _rec_name = "id"

    event_id = fields.Many2one(
        "access.passage.event", required=True, ondelete="cascade",
        index=True)
    violation_type = fields.Selection(_VIOLATION_TYPE, required=True,
                                       index=True)
    priority = fields.Selection(_PRIORITY, default="medium", required=True,
                                 index=True)
    push_sent = fields.Boolean(default=False,
        help="Whether push notification was sent to security.")
    hr_review_state = fields.Selection(
        _HR_REVIEW, default="none", required=True, index=True)
    hr_attendance_id = fields.Many2one(
        "hr.attendance", ondelete="set null",
        help="Linked attendance entry when the violation required manual "
             "създаване (HR review marker).")
    notes = fields.Text()
    company_id = fields.Many2one(
        related="event_id.company_id", store=True, index=True)
    ts = fields.Datetime(related="event_id.ts", store=True, index=True)

    def action_mark_reviewed(self):
        self.write({"hr_review_state": "reviewed"})

    def action_dismiss(self):
        self.write({"hr_review_state": "dismissed"})

    def name_get(self):
        return [(
            r.id,
            "%s %s @%s" % (
                dict(_PRIORITY).get(r.priority, "?").upper(),
                dict(_VIOLATION_TYPE).get(r.violation_type, "?"),
                r.ts.strftime("%Y-%m-%d %H:%M") if r.ts else "—",
            )
        ) for r in self]
