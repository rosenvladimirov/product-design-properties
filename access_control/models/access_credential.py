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
    department_id = fields.Many2one(
        "hr.department",
        related="holder_employee_id.department_id",
        store=True, readonly=True,
        help="Department of the employee holder (auto-derived). Used to "
             "auto-populate perimeter_ids from department defaults.")
    schedule_id = fields.Many2one(
        "resource.calendar", string="Schedule",
        compute="_compute_schedule_id", store=True, readonly=False,
        help="Working time schedule for this credential. Auto-populated "
             "from employee.resource_calendar_id; editable for visitors. "
             "The decision flow matches schedule against access.time.slot "
             "entries with the same schedule_id (slots without schedule "
             "apply to everyone).")

    @api.depends("holder_employee_id",
                 "holder_employee_id.resource_calendar_id")
    def _compute_schedule_id(self):
        for rec in self:
            if rec.holder_employee_id \
                    and rec.holder_employee_id.resource_calendar_id:
                rec.schedule_id = \
                    rec.holder_employee_id.resource_calendar_id
            elif not rec.schedule_id:
                rec.schedule_id = False

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

    @api.onchange("holder_employee_id")
    def _onchange_employee_load_dept_perimeters(self):
        """When employee picked → append department's default perimeters
        to perimeter_ids (append-only — existing perimeters kept)."""
        if not self.holder_employee_id:
            return
        dept_perimeters = self.holder_employee_id.department_id.perimeter_ids
        if not dept_perimeters:
            return
        union = set(self.perimeter_ids.ids) | set(dept_perimeters.ids)
        if union != set(self.perimeter_ids.ids):
            self.perimeter_ids = [(6, 0, list(union))]

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
        records._sync_perimeters_from_department()
        records._sync_controllers_from_perimeters()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "holder_partner_id" in vals and "subject_id" not in vals:
            self._auto_link_subject()
        if "holder_employee_id" in vals or "subject_id" in vals:
            self._sync_perimeters_from_department()
        if "perimeter_ids" in vals:
            self._sync_controllers_from_perimeters()
        return res

    def action_push_to_hardware(self):
        """Queue proxy commands to sync this credential to controllers.

        For each (linked hr.rfid.card × credential.controller_ids), one
        \`erpnet.fp.proxy.command\` row with kind='polimex.card.sync' is
        created on the controller's proxy. Proxy daemon picks it up and
        translates to Polimex SDK F0/F1 opcodes.
        """
        import json
        Command = self.env["erpnet.fp.proxy.command"].sudo()
        Card = self.env["hr.rfid.card"].sudo()
        queued = 0
        for cred in self:
            if not cred.active:
                continue
            cards = Card.search([("credential_id", "=", cred.id)])
            if not cards:
                continue
            granted_perims = cred.perimeter_ids.ids
            for card in cards:
                for controller in cred.controller_ids:
                    if not controller.proxy_id \
                            or not getattr(controller, "polimex_bus_id",
                                           False):
                        continue
                    payload = {
                        "card_number": card.card_number,
                        "controller_bus_id": controller.polimex_bus_id,
                        "active": cred.active,
                        "credential_id": cred.id,
                        "card_id": card.id,
                        "valid_from": cred.valid_from.isoformat()
                            if cred.valid_from else None,
                        "valid_to": cred.valid_to.isoformat()
                            if cred.valid_to else None,
                        "perimeter_ids": granted_perims,
                        "schedule_id": cred.schedule_id.id
                            if cred.schedule_id else None,
                    }
                    Command.create({
                        "proxy_id": controller.proxy_id.id,
                        "kind": "polimex.card.sync",
                        "payload_json": json.dumps(payload),
                        "state": "queued",
                    })
                    queued += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if queued else "warning",
                "title": _("Push to Hardware"),
                "message": _(
                    "Queued %s command(s) for proxy delivery.",
                    queued) if queued else _(
                    "No commands generated — check that the credential "
                    "is active, has linked cards, and selected "
                    "controllers have a proxy bus id."),
                "sticky": False,
            },
        }

    def _sync_perimeters_from_department(self):
        """Append-only: add department's default perimeters to credential.
        Backend version (write hook); UI is handled by onchange."""
        for rec in self:
            if not rec.holder_employee_id \
                    or not rec.holder_employee_id.department_id:
                continue
            dept_perims = rec.holder_employee_id.department_id.perimeter_ids
            if not dept_perims:
                continue
            union = set(rec.perimeter_ids.ids) | set(dept_perims.ids)
            if union != set(rec.perimeter_ids.ids):
                rec.perimeter_ids = [(6, 0, list(union))]

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
