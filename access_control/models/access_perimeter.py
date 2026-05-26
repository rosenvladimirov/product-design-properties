# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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
        help="Уникален код за програмен достъп (e.g. 'office_main', "
             "'warehouse_dock_3'). Уникален в рамките на company.")
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        "access.perimeter", string="Parent", ondelete="restrict",
        index=True,
        help="Вложен периметър. Влизане в дъщерен може да изисква "
             "присъствие в родителя (requires_parent_presence).")
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many("access.perimeter", "parent_id",
                                 string="Children")
    requires_parent_presence = fields.Boolean(
        default=False,
        help="Ако ON: за да влезе субект тук, трябва да е настоящ в "
             "parent perimeter (occupancy.state='inside'). "
             "ZEN A1 контекст: 'requires_parent_presence' + 'parent_present'.")
    enforcement = fields.Selection(
        [("soft", "Soft (advisory)"), ("strict", "Strict (block on violation)")],
        default="soft", required=True,
        help="Soft = нарушение се логва + push, но не блокира; "
             "Strict = denied + violation запис. Виж спека: fail-safe "
             "изход — никога не заключвай човек вътре.")
    calendar_id = fields.Many2one(
        "resource.calendar", string="Schedule",
        help="Темпорален прозорец. Празно = 24/7. Стандартен Odoo "
             "resource.calendar — позволява тих час/работни смени.")
    tolerance_minutes = fields.Integer(
        default=15, required=True,
        help="Мек tolerance window извън calendar (минути). 0 = строго.")
    zen_table_id = fields.Many2one(
        "zen.decision.table", string="ZEN Decision Table",
        domain="[('domain', '=', 'access')]",
        help="Override на default access decision graph за тoзи периметър. "
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
