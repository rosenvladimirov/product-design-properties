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
        help='9.5 = 09:30. Локално време на slot tz.')
    hour_to = fields.Float(string='End (hour)', required=True, default=18.0,
        help='> 24 = wrap полунощ. Напр. 30 = 06:00 следващ ден.')
    tz = fields.Selection('_tz_get', string='Timezone',
        help='Празно = company.tz')

    weekday_mon = fields.Boolean(string='Mon', default=True)
    weekday_tue = fields.Boolean(string='Tue', default=True)
    weekday_wed = fields.Boolean(string='Wed', default=True)
    weekday_thu = fields.Boolean(string='Thu', default=True)
    weekday_fri = fields.Boolean(string='Fri', default=True)
    weekday_sat = fields.Boolean(string='Sat', default=False)
    weekday_sun = fields.Boolean(string='Sun', default=False)

    controller_ids = fields.Many2many('access.controller',
        string='Controllers',
        help='Празно = всички контролери (site-wide).')
    perimeter_ids = fields.Many2many('access.perimeter',
        string='Perimeters',
        help='Празно = всички периметри.')

    date_start = fields.Date(help='Опционално начало на валидност.')
    date_end = fields.Date(help='Опционално край на валидност.')

    color = fields.Char(default='#3498DB',
        help='HEX за UI badge + SVG trail rendering.')
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
    def find_matching(self, dt_utc, controller=None, perimeter=None):
        """Връща match-ващите slot-ове за timestamp + scope."""
        slots = self.search([('active', '=', True)])
        result_ids = []
        for slot in slots:
            if controller and slot.controller_ids \
                    and controller not in slot.controller_ids:
                continue
            if perimeter and slot.perimeter_ids \
                    and perimeter not in slot.perimeter_ids:
                continue
            if slot._matches(dt_utc):
                result_ids.append(slot.id)
        return self.browse(result_ids)
