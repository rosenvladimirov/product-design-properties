# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.credential.controller — per (credential × controller) hardware
sync ledger.

`access.credential.controller_ids` (m2m on the base) остава логическият
grant-set (кои контролери приема картата, driven by perimeters). ТОЗИ
модел е паралелен ledger: 1 ред на двойка (credential, controller), който
носи hardware-specific атрибутите за "наливане" на картата:

- `hw_storage` — облачна (cloud) / локална (local) / both. Решава дали
  card.sync пише D1 в паметта на контролера или само server-validation.
- rights/ts/pin — параметрите на D1 frame-а (proxy ги превръща в wire).
- sync_state/last_sync/sync_error — статус на последния push.

Редовете се материализират лениво от controller_ids (виж
access.credential._ensure_credential_controllers). НЯМА data migration —
старите controller_ids връзки остават; ledger се пълни при пръв push.
"""

from odoo import _, api, fields, models

_HW_STORAGE = [
    ("local", "Local (burned into controller, offline)"),
    ("cloud", "Cloud (server-validated, External DB)"),
    ("both", "Both (local + cloud)"),
]

_SYNC_STATE = [
    ("pending", "Pending"),
    ("synced", "Synced"),
    ("failed", "Failed"),
]


class AccessCredentialController(models.Model):
    _name = "access.credential.controller"
    _description = "Credential ↔ Controller hardware sync ledger"
    _rec_name = "controller_id"

    credential_id = fields.Many2one(
        "access.credential", required=True, index=True, ondelete="cascade")
    controller_id = fields.Many2one(
        "access.controller", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(
        related="credential_id.company_id", store=True, index=True)

    hw_storage = fields.Selection(
        _HW_STORAGE, string="Storage", required=True, default="local",
        help="Local — the card is written into the controller's memory "
             "(D1) so it validates standalone/offline. Cloud — the "
             "controller asks the server on each read (External DB + proxy "
             "ZEN); no local write. Both — local write AND cloud "
             "validation.")

    # D1 frame parameters — defaults grant reader 1 on TS slot 1 (always).
    # Phase 3 derives these from the control-point readers + the
    # resource.calendar → Polimex TS-table mapping.
    rights_data = fields.Integer(
        "Rights Data", default=1,
        help="Per-reader bitmask granted (reader N → 1<<(N-1)).")
    rights_mask = fields.Integer(
        "Rights Mask", default=1,
        help="Which reader bits this sync sets/clears.")
    ts_code = fields.Char(
        "TS Code", size=8, default="01000000",
        help="4-byte hex Polimex Time-Schedule slot per reader "
             "(slot 1 = always). Phase 3 maps the credential schedule.")
    pin_code = fields.Char("PIN", default="0000")

    sync_state = fields.Selection(
        _SYNC_STATE, default="pending", required=True, index=True)
    last_sync = fields.Datetime("Last Sync")
    sync_error = fields.Char("Last Error")

    _sql_constraints = [
        ("credential_controller_uniq",
         "unique(credential_id, controller_id)",
         "A credential can have only one hardware-sync row per "
         "controller."),
    ]

    def _hw_op(self):
        """Resolve the proxy `hw_op` for this row: skip (cloud — no local
        write), remove (revoked / inactive credential), or add."""
        self.ensure_one()
        if self.hw_storage == "cloud":
            return "skip"
        if not self.credential_id.active:
            return "remove"
        return "add"
