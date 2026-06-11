# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.attendance.log — per-perimeter presence log с timezone.

Append-only запис на (subject, perimeter, entry_ts, exit_ts, duration,
timezone). Различно от hr.attendance (което e company-wide check_in/
check_out на работно време). Този log хроникира всяко присъствие във
всеки конкретен perimeter с time-zone awareness.

Workflow:
- passage.event direction='in'  → create open запис (exit_ts=NULL)
- passage.event direction='out' → close latest open запис
- duration_minutes се computer-ва от entry/exit разлика

Timezone resolution priority:
1. perimeter.tz (ако е set на perimeter-а)
2. subject.partner_id.tz (партньорски/служителски TZ)
3. company.partner_id.tz (companу default)

Bridge към hr.attendance е ОТДЕЛЕН модул (TBD — чака дискусия 2026-05-26).
"""

import pytz

from odoo import _, api, fields, models


class AccessAttendanceLog(models.Model):
    _name = "access.attendance.log"
    _description = "Per-perimeter Attendance Log (TZ-aware)"
    _order = "entry_ts desc"
    _rec_name = "id"

    subject_id = fields.Many2one(
        "access.subject", required=True, index=True, ondelete="cascade")
    perimeter_id = fields.Many2one(
        "access.perimeter", required=True, index=True, ondelete="restrict")
    # Related за UI / search convenience
    employee_id = fields.Many2one(
        "hr.employee", related="subject_id.employee_id", store=True,
        index=True)
    partner_id = fields.Many2one(
        "res.partner", related="subject_id.partner_id", store=True,
        index=True)
    # Времеви граници (UTC в DB, конвертират се в UI спрямо timezone)
    entry_ts = fields.Datetime(
        required=True, default=fields.Datetime.now, index=True)
    exit_ts = fields.Datetime(index=True)
    duration_minutes = fields.Float(
        compute="_compute_duration", store=True, digits=(10, 2),
        help="Minutes between entry_ts and exit_ts. NULL when exit_ts is empty "
             "(субектът още е вътре).")
    duration_hhmm = fields.Char(compute="_compute_duration")
    state = fields.Selection(
        [("inside", "Inside"), ("left", "Left")],
        compute="_compute_state", store=True, index=True)
    timezone = fields.Char(
        string="Timezone",
        help="Resolved IANA TZ name (Europe/Sofia etc.) — snapshot "
             "at entry time. Used за local-time reporting.")
    entry_local = fields.Char(
        compute="_compute_local_times", store=False,
        help="entry_ts converted in self.timezone (display only).")
    exit_local = fields.Char(
        compute="_compute_local_times", store=False)
    entry_event_id = fields.Many2one(
        "access.passage.event", ondelete="set null", string="Entry Event")
    exit_event_id = fields.Many2one(
        "access.passage.event", ondelete="set null", string="Exit Event")
    company_id = fields.Many2one(
        related="perimeter_id.company_id", store=True, index=True)

    _open_per_subject_perimeter = models.Constraint(
        # PostgreSQL partial unique — ensures само 1 open запис per
        # (subject, perimeter) едновременно. Closed records (exit_ts SET)
        # са изключени.
        "CHECK (exit_ts IS NULL OR exit_ts >= entry_ts)",
        "exit_ts must be >= entry_ts.",
    )

    @api.depends("entry_ts", "exit_ts")
    def _compute_duration(self):
        for rec in self:
            if rec.entry_ts and rec.exit_ts:
                delta = rec.exit_ts - rec.entry_ts
                rec.duration_minutes = delta.total_seconds() / 60.0
                h, m = divmod(int(rec.duration_minutes), 60)
                rec.duration_hhmm = f"{h:02d}:{m:02d}"
            else:
                rec.duration_minutes = False
                rec.duration_hhmm = False

    @api.depends("exit_ts")
    def _compute_state(self):
        for rec in self:
            rec.state = "left" if rec.exit_ts else "inside"

    @api.depends("entry_ts", "exit_ts", "timezone")
    def _compute_local_times(self):
        for rec in self:
            tz = pytz.timezone(rec.timezone) if rec.timezone else None
            if rec.entry_ts and tz:
                rec.entry_local = pytz.utc.localize(rec.entry_ts).astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
            else:
                rec.entry_local = rec.entry_ts.strftime("%Y-%m-%d %H:%M UTC") if rec.entry_ts else False
            if rec.exit_ts and tz:
                rec.exit_local = pytz.utc.localize(rec.exit_ts).astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
            else:
                rec.exit_local = rec.exit_ts.strftime("%Y-%m-%d %H:%M UTC") if rec.exit_ts else False

    # ── Lifecycle helpers (called от access.decision.flow) ────────
    @api.model
    def open_entry(self, subject, perimeter, event, ts=None):
        """Create нов open запис при entry passage. Resolves timezone."""
        if not subject or not perimeter:
            return self.browse()
        ts = ts or fields.Datetime.now()
        tz = self._resolve_timezone(subject, perimeter)
        # Защита: затвори всички предишни open записи за тоi (subject,
        # perimeter) — анти-duplicate safety
        open_records = self.sudo().search([
            ("subject_id", "=", subject.id),
            ("perimeter_id", "=", perimeter.id),
            ("exit_ts", "=", False),
        ])
        if open_records:
            open_records.write({"exit_ts": ts})
        return self.sudo().create({
            "subject_id": subject.id,
            "perimeter_id": perimeter.id,
            "entry_ts": ts,
            "timezone": tz,
            "entry_event_id": event.id if event else False,
        })

    @api.model
    def close_exit(self, subject, perimeter, event, ts=None):
        """Затваря latest open запис при exit passage."""
        if not subject or not perimeter:
            return self.browse()
        ts = ts or fields.Datetime.now()
        open_rec = self.sudo().search([
            ("subject_id", "=", subject.id),
            ("perimeter_id", "=", perimeter.id),
            ("exit_ts", "=", False),
        ], order="entry_ts desc", limit=1)
        if open_rec:
            open_rec.write({
                "exit_ts": ts,
                "exit_event_id": event.id if event else False,
            })
        return open_rec

    @api.model
    def _resolve_timezone(self, subject, perimeter):
        """Priority: perimeter.tz → subject.partner.tz → company.tz → UTC."""
        # access.perimeter няма tz field в Phase 2 base модела —
        # ползваме calendar_id.tz ако е set
        if perimeter and perimeter.calendar_id and perimeter.calendar_id.tz:
            return perimeter.calendar_id.tz
        if subject:
            partner = subject.partner_id
            if partner and partner.tz:
                return partner.tz
            employee = subject.employee_id
            if employee and employee.tz:
                return employee.tz
        if perimeter and perimeter.company_id and perimeter.company_id.partner_id.tz:
            return perimeter.company_id.partner_id.tz
        return "UTC"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    access_attendance_log_count = fields.Integer(
        compute="_compute_access_attendance_log_count")
    access_attendance_total_minutes = fields.Float(
        compute="_compute_access_attendance_log_count",
        help="Total minutes present across all perimeters (closed records).")

    def _compute_access_attendance_log_count(self):
        Log = self.env["access.attendance.log"].sudo()
        for emp in self:
            logs = Log.search([("employee_id", "=", emp.id)])
            emp.access_attendance_log_count = len(logs)
            emp.access_attendance_total_minutes = sum(
                logs.mapped("duration_minutes"))

    def action_open_access_attendance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Perimeter Attendance"),
            "res_model": "access.attendance.log",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
        }


class ResPartner(models.Model):
    _inherit = "res.partner"

    access_attendance_log_count = fields.Integer(
        compute="_compute_access_attendance_log_count")

    def _compute_access_attendance_log_count(self):
        Log = self.env["access.attendance.log"].sudo()
        for p in self:
            p.access_attendance_log_count = Log.search_count(
                [("partner_id", "=", p.id)])

    def action_open_access_attendance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Perimeter Attendance"),
            "res_model": "access.attendance.log",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
        }
