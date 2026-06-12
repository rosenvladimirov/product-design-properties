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
"""access.perimeter — вложен периметър с темпорални прозорци.

Перимerite се влагат йерархично (parent_id). Влизане в дъщерен периметър
може да изисква присъствие в родителя (`requires_parent_presence`).
Темпоралния прозорец стъпва на resource.calendar (стандартен Odoo
паттерн); tolerance_minutes е per-perimeter поле (Open Q#3 — Rosen
2026-05-26: per perimeter, не глобален constant).
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccessPerimeter(models.Model):
    _name = "access.perimeter"
    _description = "Access Perimeter (nested zone with temporal windows)"
    _order = "parent_id, sequence, name"
    _parent_store = True
    _parent_name = "parent_id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Unique code for programmatic access (e.g. 'office_main', "
             "'warehouse_dock_3'). Уникален в рамките на company.")
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        "access.perimeter", string="Parent", ondelete="restrict",
        index=True,
        help="Nested perimeter. Entry to a child may require "
             "присъствие в родителя (requires_parent_presence).")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("access.perimeter", "parent_id",
                                 string="Children")
    requires_parent_presence = fields.Boolean(
        default=False,
        help="If ON: to enter, a subject must currently be present in "
             "parent perimeter (occupancy.state='inside'). "
             "ZEN A1 контекст: 'requires_parent_presence' + 'parent_present'.")
    enforcement = fields.Selection(
        [("soft", "Soft (advisory)"), ("strict", "Strict (block on violation)")],
        default="soft", required=True,
        help="Soft = violation is logged + push, but not blocked; "
             "Strict = denied + violation запис. Виж спека: fail-safe "
             "изход — никога не заключвай човек вътре.")
    calendar_id = fields.Many2one(
        "resource.calendar", string="Schedule",
        help="Temporal window. Empty = 24/7. Standard Odoo "
             "resource.calendar — позволява тих час/работни смени.")
    tolerance_minutes = fields.Integer(
        default=15, required=True,
        help="Soft tolerance window outside the calendar (minutes). 0 = strict.")
    zen_table_id = fields.Many2one(
        "zen.decision.table", string="ZEN Decision Table",
        domain="[('domain', '=', 'access')]",
        help="Override of the default access decision graph for this perimeter. "
             "Празно = използва default 'access_default' table.")
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True,
        required=True)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Each perimeter code must be unique per company.",
    )

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(
                _("Perimeter cannot have a recursive parent."))

    @api.constrains("requires_parent_presence", "parent_id")
    def _check_requires_parent_has_parent(self):
        for rec in self:
            if rec.requires_parent_presence and not rec.parent_id:
                raise ValidationError(
                    _("Perimeter '%(name)s' has requires_parent_presence "
                      "but no parent.", name=rec.name))

    def _perimeter_chain(self):
        """Return list of parents from root to self (inclusive). Used
        by context builder for spatial dimension."""
        self.ensure_one()
        chain = []
        node = self
        while node:
            chain.insert(0, node)
            node = node.parent_id
        return chain

    # Smart button counts
    occupancy_inside_count = fields.Integer(
        compute="_compute_perimeter_stats",
        help="Currently inside the perimeter.")
    passage_today_count = fields.Integer(
        compute="_compute_perimeter_stats",
        help="Passage events count for today.")

    @api.depends_context("uid")
    def _compute_perimeter_stats(self):
        Occ = self.env["access.occupancy"].sudo()
        Event = self.env["access.passage.event"].sudo()
        from datetime import datetime, time
        today = datetime.combine(datetime.utcnow().date(), time.min)
        for rec in self:
            rec.occupancy_inside_count = Occ.search_count([
                ("perimeter_id", "=", rec.id),
                ("state", "=", "inside"),
            ])
            rec.passage_today_count = Event.search_count([
                ("perimeter_id", "=", rec.id),
                ("ts", ">=", today),
            ])

    def action_open_heatmap(self):
        """Open SVG heatmap в нов tab."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/access_control/svg/heatmap/{self.id}?days=30",
            "target": "new",
        }

    def action_open_perimeter_occupancy(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inside %s", self.name),
            "res_model": "access.occupancy",
            "view_mode": "kanban,list",
            "domain": [("perimeter_id", "=", self.id), ("state", "=", "inside")],
        }

    def action_open_perimeter_passages(self):
        self.ensure_one()
        from datetime import datetime, time
        today = datetime.combine(datetime.utcnow().date(), time.min)
        return {
            "type": "ir.actions.act_window",
            "name": _("Today's passages — %s", self.name),
            "res_model": "access.passage.event",
            "view_mode": "kanban,list,graph,pivot",
            "domain": [
                ("perimeter_id", "=", self.id),
                ("ts", ">=", today),
            ],
        }

    def _resolve_window(self, ts):
        """Return (start, end) for the active calendar window covering ts.
        None если 24/7 (calendar_id празно)."""
        self.ensure_one()
        if not self.calendar_id:
            return None
        # TODO: implement за следваща итерация (use resource.calendar
        # methods like _attendance_intervals_batch). За сега placeholder
        # за context builder fallback.
        return None
