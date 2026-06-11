# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.occupancy — текущо състояние per (subject, perimeter).

Една row per (subject_id, perimeter_id) — UPSERT при всеки passage event.
state = inside/outside/unknown. Last_seen и entered_at updates съответно.

Important per спека: occupancy = СЪВЕТВАЩА за изход; никога не блокира.
"""

from odoo import api, fields, models


_STATE = [
    ("inside", "Inside"),
    ("outside", "Outside"),
    ("unknown", "Unknown"),
]


class AccessOccupancy(models.Model):
    _name = "access.occupancy"
    _description = "Access Occupancy (current state per subject/perimeter)"
    _order = "last_seen desc"

    subject_id = fields.Many2one(
        "access.subject", required=True, index=True, ondelete="cascade")
    perimeter_id = fields.Many2one(
        "access.perimeter", required=True, index=True, ondelete="cascade")
    state = fields.Selection(_STATE, default="unknown", required=True,
                              index=True)
    entered_at = fields.Datetime(
        help="Last 'inside' transition timestamp.")
    last_seen = fields.Datetime(
        help="Last passage event timestamp on this perimeter.")
    last_event_id = fields.Many2one(
        "access.passage.event", ondelete="set null")
    company_id = fields.Many2one(
        related="perimeter_id.company_id", store=True, index=True)

    _subject_perimeter_uniq = models.Constraint(
        "unique(subject_id, perimeter_id)",
        "One occupancy row per (subject, perimeter).",
    )

    @api.model
    def upsert(self, subject_id, perimeter_id, direction, event_id, ts):
        """Update existing or create new occupancy row.
        direction='in' → state=inside, entered_at=ts
        direction='out' → state=outside
        direction=None (anomaly) → state=unknown, не променя entered_at."""
        existing = self.sudo().search([
            ("subject_id", "=", subject_id),
            ("perimeter_id", "=", perimeter_id),
        ], limit=1)
        if direction == "in":
            new_state = "inside"
            vals = {"state": "inside", "entered_at": ts}
        elif direction == "out":
            new_state = "outside"
            vals = {"state": "outside"}
        else:
            new_state = "unknown"
            vals = {"state": "unknown"}
        vals.update({"last_seen": ts, "last_event_id": event_id})
        if existing:
            existing.sudo().write(vals)
            return existing
        return self.sudo().create(dict(vals, subject_id=subject_id,
                                        perimeter_id=perimeter_id))
