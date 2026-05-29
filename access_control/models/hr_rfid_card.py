# -*- coding: utf-8 -*-
"""Quick onboard: смартутон 'Credential' на hr.rfid.card form.

Workflow за нов служител:
  1. Card master record (hr.rfid.card) — existing or created from RFID event
  2. Click 'Credential' smart button → opens/creates linked access.credential
  3. Credential form auto-populates department perimeters + holder
  4. One click → access rights configured
"""
from odoo import _, models


class HrRfidCard(models.Model):
    _inherit = "hr.rfid.card"

    def action_open_or_create_credential(self):
        """Open the linked access.credential, creating one when missing.

        Auto-binds the appropriate holder (employee work_contact or
        partner) from card metadata."""
        self.ensure_one()
        if not self.credential_id:
            partner = self.partner_id
            if not partner and self.employee_id:
                partner = self.employee_id.work_contact_id
            if not partner:
                from odoo.exceptions import UserError
                raise UserError(_(
                    "Card has no linked employee or partner. Set holder "
                    "first, then create the credential."))
            cred_vals = {
                "credential_kind": "card",
                "holder_partner_id": partner.id,
            }
            cred = self.env["access.credential"].sudo().create(cred_vals)
            self.credential_id = cred.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Access Credential — %s", self.card_number),
            "res_model": "access.credential",
            "res_id": self.credential_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
