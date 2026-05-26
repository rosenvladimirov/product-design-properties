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
        help="Perimeters that accept this credential. Controllers са вече "
             "на base модела (controller_ids). Perimeters работят на по-"
             "висок логически слой — групиране на множество controllers.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._auto_link_subject()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "holder_partner_id" in vals and "subject_id" not in vals:
            self._auto_link_subject()
        return res

    def _auto_link_subject(self):
        """Auto-create/link access.subject when holder_partner_id is set
        but subject_id is empty. Idempotent."""
        Subject = self.env["access.subject"].sudo()
        for rec in self:
            if rec.subject_id or not rec.holder_partner_id:
                continue
            existing = Subject.search([
                ("partner_id", "=", rec.holder_partner_id.id),
                ("company_id", "=", rec.company_id.id or False),
            ], limit=1)
            if existing:
                rec.subject_id = existing
            else:
                rec.subject_id = Subject.create({
                    "name": rec.holder_partner_id.display_name,
                    "partner_id": rec.holder_partner_id.id,
                    "company_id": rec.company_id.id or False,
                })
