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
"""access.controller.time.schedule — огледало на onboard TS слот на
Polimex контролер (D3 Write Time Schedules).

За offline enforcement (Phase 3 = Option B): local карта реферира TS слот
номер; контролерът пази седмичните прозорци локално и решава самостоятелно
при network loss. Този модел мапва resource.calendar → TS слот per
контролер и държи allocated `ts_number`-а.

Mapping политика (access-control интерпретация): per ден прозорецът е
[най-ранен hour_from, най-късен hour_to] на attendance линиите (обедът се
ВКЛЮЧВА — хората влизат/излизат свободно). Holiday (ден 7) = празен.
Без schedule → "always" (00:00-24:00 всеки ден). Ръчен override възможен
по-късно през week_json.
"""

import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Polimex TS таблици на контролер (типично 0..63; слот 0 = "no access").
# Резервираме слот 1 за "always"; specific schedules от 2 нагоре.
_TS_ALWAYS = 1
_TS_MIN_ALLOC = 2
_TS_MAX = 63


class AccessControllerTimeSchedule(models.Model):
    _name = "access.controller.time.schedule"
    _description = "Controller onboard Time-Schedule slot (Polimex D3)"
    _order = "controller_id, ts_number"
    _rec_name = "display_name"

    controller_id = fields.Many2one(
        "access.controller", required=True, index=True, ondelete="cascade")
    ts_number = fields.Integer(
        "TS Slot", required=True,
        help="Time-Schedule slot number in the controller's onboard table "
             "(referenced by the card's ts_code per reader).")
    schedule_id = fields.Many2one(
        "resource.calendar", string="Schedule", ondelete="cascade",
        help="Source working time. Empty = the 'always' (24/7) slot.")
    display_name = fields.Char(compute="_compute_display_name")
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True)

    last_sync = fields.Datetime("Last D3 Sync")

    _sql_constraints = [
        ("controller_ts_uniq", "unique(controller_id, ts_number)",
         "TS slot number must be unique per controller."),
    ]

    @api.depends("controller_id", "ts_number", "schedule_id")
    def _compute_display_name(self):
        for rec in self:
            label = rec.schedule_id.name or _("Always")
            rec.display_name = "[%s] %s" % (rec.ts_number, label)

    # ── Week-interval derivation (resource.calendar → 8-day spec) ────
    def _build_week(self):
        """Return the 8-day interval spec for the proxy D3 builder:
        [[[begin, end], ...] per day] × 8 (0=Mon … 6=Sun, 7=Holiday).

        Always-slot (no schedule) → 24/7 on days 0-6, holiday empty.
        Otherwise one interval/day = [earliest hour_from, latest hour_to]
        of the schedule's attendance lines (lunch included)."""
        self.ensure_one()
        if not self.schedule_id:
            return [[[0.0, 24.0]] for _d in range(7)] + [[]]
        per_day = {d: [] for d in range(7)}
        for att in self.schedule_id.attendance_ids:
            try:
                d = int(att.dayofweek)  # Odoo 0=Mon … 6=Sun = Polimex order
            except (TypeError, ValueError):
                continue
            if 0 <= d <= 6:
                per_day[d].append((att.hour_from, att.hour_to))
        week = []
        for d in range(7):
            ivals = per_day[d]
            if ivals:
                week.append([[min(h for h, _e in ivals),
                              max(e for _h, e in ivals)]])
            else:
                week.append([])
        week.append([])  # day 7 = Holiday (empty by default)
        return week

    def _ts_payload(self):
        """Payload for the proxy `polimex.ts.sync` command."""
        self.ensure_one()
        return {
            "access_id": self.controller_id.proxy_access_id,
            "ts_number": self.ts_number,
            "week": self._build_week(),
            "schedule_id": self.schedule_id.id or None,
        }
