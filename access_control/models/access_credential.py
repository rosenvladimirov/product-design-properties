# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.credential extension — добавя subject_id link.

⚠️ ДИЗАЙН РЕШЕНИЕ (2026-05-26):
Според плана access.credential ТРЯБВА да се мести от hr_attendance_
access_control в access_control. НО това би създало circular dependency:
- hr_aac.hr.rfid.card._inherits = {'access.credential': 'credential_id'}
- следователно hr_aac NEEDS access.credential model
- ако access_control я defines, hr_aac трябва да depend на access_control
- НО access_control depend на hr_aac (за access.controller wrapper)
- ⛔ CYCLE

Решение в две стъпки:
1. **Стъпка 1 (this commit):** access_control EXTEND-ва access.credential
   (_inherit, не _name) и добавя subject_id + perimeter_ids. Primary
   ownership остава в hr_aac. Това отключва Phase 2 функционалност без
   риск от migration breakage на live DB (access-control prod има 2
   cards с credential_id вече backfilled от Phase 2 на hr_aac 5.10.0).
2. **Стъпка 2 (бъдеща, separate PR):** реален move — премахни класа
   от hr_aac, deprecate access.controller в hr_aac (или го move в
   access_control като access.proxy.endpoint), break cycle, finalize
   ownership transfer. Migration: ir_model_data rename.
"""

from odoo import _, api, fields, models


class AccessCredential(models.Model):
    _inherit = "access.credential"

    subject_id = fields.Many2one(
        "access.subject", string="Subject", index=True,
        help="Identity that holds this credential. Auto-populated from "
             "holder_partner_id when possible.")
    perimeter_ids = fields.Many2many(
        "access.perimeter", relation="access_credential_perimeter_rel",
        column1="credential_id", column2="perimeter_id",
        string="Allowed Perimeters",
        help="Perimeters that accept this credential. Controllers live "
             "on the base model (controller_ids). Perimeters work on a "
             "higher logical layer — grouping multiple controllers.")
    holder_kind = fields.Selection([
        ("employee", "Employee"),
        ("visitor", "Visitor"),
    ], compute="_compute_holder_kind", store=True, readonly=True,
        help="Auto-derived from the linked subject: 'employee' if the "
             "subject has employee_id, otherwise 'visitor'.")
    holder_employee_id = fields.Many2one(
        "hr.employee", string="Holder",
        related="subject_id.employee_id", readonly=False, store=True,
        help="Employee holder (when holder_kind = employee).")

    @api.depends("subject_id", "subject_id.employee_id",
                 "subject_id.partner_id", "holder_partner_id")
    def _compute_holder_kind(self):
        for rec in self:
            emp = rec.subject_id.employee_id
            if emp:
                rec.holder_kind = "employee"
            elif rec.holder_partner_id or rec.subject_id.partner_id:
                rec.holder_kind = "visitor"
            else:
                rec.holder_kind = False

    @api.onchange("perimeter_ids")
    def _onchange_perimeter_populate_controllers(self):
        """Когато selected perimeters се променят → auto-зареди
        controllers (access.controller) от cp.controller_id на всички
        active control_points в избраните perimeters.

        Append-only — НЕ премахва existing controllers (user-ът може
        да добави extra controllers ръчно)."""
        if not self.perimeter_ids:
            return
        CP = self.env["access.control.point"].sudo()
        cps = CP.search([
            ("perimeter_id", "in", self.perimeter_ids.ids),
            ("active", "=", True),
            ("controller_id", "!=", False),
        ])
        new_ctrl_ids = set(cps.mapped("controller_id.id"))
        existing_ids = set(self.controller_ids.ids)
        union = new_ctrl_ids | existing_ids
        if union != existing_ids:
            self.controller_ids = [(6, 0, list(union))]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._auto_link_subject()
        records._sync_controllers_from_perimeters()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "holder_partner_id" in vals and "subject_id" not in vals:
            self._auto_link_subject()
        if "perimeter_ids" in vals:
            self._sync_controllers_from_perimeters()
        return res

    def _sync_controllers_from_perimeters(self):
        """Backend version на _onchange_perimeter_populate_controllers —
        викан при create/write на perimeter_ids (когато промяната идва
        от backend код, не от UI onchange)."""
        CP = self.env["access.control.point"].sudo()
        for rec in self:
            if not rec.perimeter_ids:
                continue
            cps = CP.search([
                ("perimeter_id", "in", rec.perimeter_ids.ids),
                ("active", "=", True),
                ("controller_id", "!=", False),
            ])
            new_ctrl_ids = set(cps.mapped("controller_id.id"))
            existing_ids = set(rec.controller_ids.ids)
            union = new_ctrl_ids | existing_ids
            if union != existing_ids:
                rec.controller_ids = [(6, 0, list(union))]

    def _auto_link_subject(self):
        """Auto-create/link access.subject when holder_partner_id is set
        but subject_id is empty. Idempotent.

        Ако partner-ът е work_contact на hr.employee → subject.employee_id
        също се попълва (за да се появи в Passage Events Employee колоната
        и да работи bridge към hr.attendance)."""
        Subject = self.env["access.subject"].sudo()
        Employee = self.env["hr.employee"].sudo()
        for rec in self:
            if rec.subject_id or not rec.holder_partner_id:
                continue
            partner = rec.holder_partner_id
            existing = Subject.search([
                ("partner_id", "=", partner.id),
                ("company_id", "=", rec.company_id.id or False),
            ], limit=1)
            # Намери hr.employee който има тoзи partner като work_contact
            emp = Employee.search([
                ("work_contact_id", "=", partner.id),
            ], limit=1)
            if existing:
                # Backfill employee_id ако липсва
                if emp and not existing.employee_id:
                    existing.employee_id = emp.id
                rec.subject_id = existing
            else:
                vals = {
                    "name": partner.display_name,
                    "partner_id": partner.id,
                    "company_id": rec.company_id.id or False,
                }
                if emp:
                    vals["employee_id"] = emp.id
                rec.subject_id = Subject.create(vals)
