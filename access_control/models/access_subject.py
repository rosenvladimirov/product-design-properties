# Copyright 2026 BL Consulting
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
        help="External / visitor identity. Mutually exclusive с employee_id "
             "за чисти Subject-и; може да коexist-ват ако HR contact-ът "
             "съвпада с visitor partner-а.")
    employee_id = fields.Many2one(
        "hr.employee", string="Employee",
        help="Internal identity. Auto-populates partner_id от work_contact_id.")
    credential_ids = fields.One2many(
        "access.credential", "subject_id", string="Credentials")
    credential_count = fields.Integer(compute="_compute_credential_count")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company, index=True)
    notes = fields.Text()

    @api.depends("credential_ids")
    def _compute_credential_count(self):
        for rec in self:
            rec.credential_count = len(rec.credential_ids)

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
