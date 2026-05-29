# -*- coding: utf-8 -*-
"""access.time.slot — site/door-scoped time windows.

Не дублира resource.calendar (employee work hours). Покрива:
- night shifts на врата (hour_to > 24 = wrap полунощ)
- entry_window / exit_window политики
- lunch overrides на site ниво
- custom policy windows

За employee work hours използвай
`resource.calendar._attendance_intervals_batch` директно.
"""
import datetime
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccessTimeSlot(models.Model):
    _name = 'access.time.slot'
    _description = 'Access Control Time Slot'
    _order = 'sequence, hour_from'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    slot_type = fields.Selection([
        ('work_hours', 'Work Hours (template)'),
        ('night_shift', 'Night Shift'),
        ('entry_window', 'Entry Window'),
        ('exit_window', 'Exit Window'),
        ('lunch', 'Lunch Break'),
        ('after_hours', 'After Hours / Forbidden'),
        ('custom', 'Custom'),
    ], required=True, default='custom', index=True)

    hour_from = fields.Float(string='Start (hour)', required=True, default=9.0,
        help='9.5 = 09:30. Local time of slot tz.')
    hour_to = fields.Float(string='End (hour)', required=True, default=18.0,
        help='> 24 = wraps past midnight. E.g. 30 = 06:00 next day.')
    tz = fields.Selection('_tz_get', string='Timezone',
        help='Empty = company.tz')

    weekday_mon = fields.Boolean(string='Mon', default=True)
    weekday_tue = fields.Boolean(string='Tue', default=True)
    weekday_wed = fields.Boolean(string='Wed', default=True)
    weekday_thu = fields.Boolean(string='Thu', default=True)
    weekday_fri = fields.Boolean(string='Fri', default=True)
    weekday_sat = fields.Boolean(string='Sat', default=False)
    weekday_sun = fields.Boolean(string='Sun', default=False)

    schedule_id = fields.Many2one(
        'resource.calendar', string='Schedule',
        help='Working time schedule this slot applies to. When set, the '
             'slot is only considered for credentials whose schedule '
             'matches. Empty = applies to all schedules.')
    schedule_first_hour = fields.Float(
        string='Schedule Day Start',
        compute='_compute_schedule_summary',
        help='Earliest hour_from across all non-lunch attendance lines '
             'on the linked schedule. Compare against hour_from to verify.')
    schedule_last_hour = fields.Float(
        string='Schedule Day End',
        compute='_compute_schedule_summary',
        help='Latest hour_to across all non-lunch attendance lines on '
             'the linked schedule. Compare against hour_to to verify.')
    schedule_summary = fields.Char(
        string='Schedule Summary',
        compute='_compute_schedule_summary',
        help='Human-readable summary: "Mon-Fri 09:00-18:00 (lunch 12:00-13:00)".')

    @api.depends('schedule_id', 'schedule_id.attendance_ids')
    def _compute_schedule_summary(self):
        for rec in self:
            cal = rec.schedule_id
            if not cal or not cal.attendance_ids:
                rec.schedule_first_hour = 0.0
                rec.schedule_last_hour = 0.0
                rec.schedule_summary = False
                continue
            non_lunch = cal.attendance_ids.filtered(
                lambda a: a.day_period != 'lunch')
            lunch = cal.attendance_ids.filtered(
                lambda a: a.day_period == 'lunch')
            if non_lunch:
                rec.schedule_first_hour = min(non_lunch.mapped('hour_from'))
                rec.schedule_last_hour = max(non_lunch.mapped('hour_to'))
            else:
                rec.schedule_first_hour = min(
                    cal.attendance_ids.mapped('hour_from'))
                rec.schedule_last_hour = max(
                    cal.attendance_ids.mapped('hour_to'))
            # Day range
            days_used = sorted(set(int(a.dayofweek)
                                    for a in cal.attendance_ids))
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            if days_used and days_used == list(range(days_used[0],
                                                      days_used[-1] + 1)):
                day_str = f"{day_names[days_used[0]]}-{day_names[days_used[-1]]}"
            else:
                day_str = ",".join(day_names[d] for d in days_used)
            # Hours
            def _h(f):
                return f"{int(f):02d}:{int((f - int(f)) * 60):02d}"
            main = f"{_h(rec.schedule_first_hour)}-{_h(rec.schedule_last_hour)}"
            extra = ""
            if lunch:
                lf = min(lunch.mapped('hour_from'))
                lt = max(lunch.mapped('hour_to'))
                extra = f" (lunch {_h(lf)}-{_h(lt)})"
            rec.schedule_summary = f"{day_str} {main}{extra}"
    controller_ids = fields.Many2many('access.controller',
        string='Controllers',
        help='Empty = all controllers (site-wide).')
    perimeter_ids = fields.Many2many('access.perimeter',
        string='Perimeters',
        help='Empty = all perimeters.')

    date_start = fields.Date(help='Optional validity start date.')
    date_end = fields.Date(help='Optional validity end date.')

    color = fields.Char(default='#3498DB',
        help='HEX color for UI badge + SVG trail rendering.')
    notes = fields.Text()

    company_id = fields.Many2one('res.company',
        default=lambda s: s.env.company, required=True)

    @api.model
    def _tz_get(self):
        return self.env['res.partner']._fields['tz'].selection

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for rec in self:
            if not (0 <= rec.hour_from < 24):
                raise ValidationError(_(
                    "Start hour must be in [0, 24): %s", rec.hour_from))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_(
                    "End hour (%s) must be > start hour (%s). За night "
                    "shift пиши end > 24 (e.g. 30 = 06:00 next day).",
                    rec.hour_to, rec.hour_from))
            if rec.hour_to > 48:
                raise ValidationError(_(
                    "End hour > 48 е твърде голямо (%s).", rec.hour_to))

    def _weekday_active(self, py_weekday):
        """py_weekday: 0=Monday … 6=Sunday."""
        self.ensure_one()
        return [
            self.weekday_mon, self.weekday_tue, self.weekday_wed,
            self.weekday_thu, self.weekday_fri, self.weekday_sat,
            self.weekday_sun,
        ][py_weekday]

    def _matches(self, dt_utc):
        """Връща True ако slot-ът match-ва UTC datetime."""
        self.ensure_one()
        if not self.active:
            return False
        if self.date_start and dt_utc.date() < self.date_start:
            return False
        if self.date_end and dt_utc.date() > self.date_end:
            return False
        tz_name = self.tz or self.company_id.partner_id.tz or 'UTC'
        tz = pytz.timezone(tz_name)
        if dt_utc.tzinfo is None:
            dt_utc = pytz.utc.localize(dt_utc)
        local = dt_utc.astimezone(tz)
        h = local.hour + local.minute / 60.0
        if self.hour_to <= 24:
            # Прост случай — same-day window
            return (self._weekday_active(local.weekday())
                    and self.hour_from <= h < self.hour_to)
        # Wrap night shift: [hour_from, 24) ∪ [0, hour_to - 24) of next day
        if h >= self.hour_from \
                and self._weekday_active(local.weekday()):
            return True
        if h < (self.hour_to - 24):
            prev = local - datetime.timedelta(days=1)
            return self._weekday_active(prev.weekday())
        return False

    @api.model
    def find_matching(self, dt_utc, controller=None, perimeter=None,
                      schedule=None):
        """Returns matching slots for timestamp + scope + schedule.

        When `schedule` is provided (resource.calendar of the credential),
        slots with schedule_id set are kept only if they match. Slots
        without schedule_id always apply (general policy)."""
        slots = self.search([('active', '=', True)])
        result_ids = []
        for slot in slots:
            if controller and slot.controller_ids \
                    and controller not in slot.controller_ids:
                continue
            if perimeter and slot.perimeter_ids \
                    and perimeter not in slot.perimeter_ids:
                continue
            if slot.schedule_id and schedule \
                    and slot.schedule_id != schedule:
                continue
            if slot._matches(dt_utc):
                result_ids.append(slot.id)
        return self.browse(result_ids)
