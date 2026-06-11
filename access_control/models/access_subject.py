# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.subject — групира носителите (credentials) на едно физическо лице.

1 субект може да държи карта + биометрия + регистрационен номер на кола
едновременно. Subject е connection point към hr.employee / res.partner —
позволява всички credential типове да резолват към една и съща identity
при decision evaluation.
"""

from odoo import _, api, fields, models


class AccessSubject(models.Model):
    _name = "access.subject"
    _description = "Access Subject (groups multiple credentials per identity)"
    _order = "name"

    name = fields.Char(required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Partner",
        help="External / visitor identity. Mutually exclusive with employee_id "
             "за чисти Subject-и; може да коexist-ват ако HR contact-ът "
             "съвпада с visitor partner-а.")
    employee_id = fields.Many2one(
        "hr.employee", string="Employee",
        help="Internal identity. Auto-populates partner_id from work_contact_id.")
    credential_ids = fields.One2many(
        "access.credential", "subject_id", string="Credentials")
    credential_count = fields.Integer(compute="_compute_credential_count")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True)
    notes = fields.Text()

    current_location = fields.Char(
        compute="_compute_current_location",
        help="Live occupancy summary — which perimeters the subject is currently "
             "вътре. Computed (non-stored) → винаги fresh.")
    inside_count = fields.Integer(
        compute="_compute_current_location",
        help="Count of perimeters where the subject is currently inside.")
    last_activity = fields.Datetime(
        compute="_compute_current_location",
        help="Last passage event timestamp.")

    @api.depends("credential_ids")
    def _compute_credential_count(self):
        for rec in self:
            rec.credential_count = len(rec.credential_ids)

    @api.depends_context("uid")
    def _compute_current_location(self):
        Occ = self.env["access.occupancy"].sudo()
        for rec in self:
            inside = Occ.search([
                ("subject_id", "=", rec.id),
                ("state", "=", "inside"),
            ])
            rec.inside_count = len(inside)
            rec.current_location = (
                ", ".join(inside.mapped("perimeter_id.code"))
                if inside else "—")
            rec.last_activity = max(
                inside.mapped("last_seen"), default=False)

    def action_open_today_passages(self):
        self.ensure_one()
        from datetime import datetime, time
        today = datetime.combine(datetime.utcnow().date(), time.min)
        return {
            "type": "ir.actions.act_window",
            "name": _("Today's Passages"),
            "res_model": "access.passage.event",
            "view_mode": "kanban,list,form",
            "domain": [
                ("subject_id", "=", self.id),
                ("ts", ">=", today),
            ],
        }

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id and not self.partner_id:
            self.partner_id = self.employee_id.work_contact_id
        if self.employee_id and not self.name:
            self.name = self.employee_id.name

    def action_open_credentials(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Credentials"),
            "res_model": "access.credential",
            "view_mode": "list,form",
            "domain": [("subject_id", "=", self.id)],
            "context": {"default_subject_id": self.id},
        }
