# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.control.point — физическа точка за достъп.

Различен от access.controller (network HTTP wrapper в hr_aac). Control
point е физическа точка с конкретни parts (2 readers + magnet + door).
От signal matrix-а на тези parts се извежда direction (Python helper в
context builder, виж секция 4.3 от плана).

Connects to access.controller (legacy HTTP wrapper) чрез soft m2o
(comodel='access.controller', ondelete='set null') — за да pulse-неш
магнита трябва да викнеш controller.open() (hr_aac бекенд).
"""

from odoo import fields, models


_DIRECTION_KIND = [
    ("in", "Entry only"),
    ("out", "Exit only"),
    ("bidirectional", "Bidirectional (turnstile / single door)"),
]


class AccessControlPoint(models.Model):
    _name = "access.control.point"
    _description = "Access Control Point (physical signal matrix)"
    _order = "perimeter_id, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Unique code (e.g. 'office_main_front_door').")
    perimeter_id = fields.Many2one(
        "access.perimeter", required=True, ondelete="restrict", index=True)
    direction_kind = fields.Selection(
        _DIRECTION_KIND, default="bidirectional", required=True,
        help="Whether this point supports entry only, exit only, or "
             "и двете (turnstile с external/internal reader).")
    # Soft m2o към hr_aac.access.controller — без hard depend в depends
    # списъка би било проблем (вече depend-ваме на hr_aac, OK).
    controller_id = fields.Many2one(
        "access.controller", string="HTTP Controller (proxy wrapper)",
        ondelete="set null",
        help="Network endpoint in proxy to push commands to "
             "магнита. Празно = manual/observational point (read-only).")
    # Parts — конкретните физически компоненти.
    # ⚠️ В Phase 2 (initial) тези са Char placeholder-и за reader/magnet/
    # door IDs от proxy config.d/access.yaml. В future Phase 3 ще се
    # превърнат в M2O към нов access.controller.part модел (или
    # access.proxy.device — TBD според бъдеща итерация).
    external_reader_id = fields.Char(
        string="External Reader ID",
        help="Proxy reader id (entry-side button). Empty = no physical "
             "external reader (only-exit точка).")
    internal_reader_id = fields.Char(
        string="Internal Reader ID",
        help="Proxy reader id (exit-side button).")
    magnet_id = fields.Char(
        string="Magnet/Lock ID",
        help="Proxy magnet/lock id. Pulsing this fires the door open.")
    door_sensor_id = fields.Char(
        string="Door Sensor ID",
        help="Proxy door sensor id (open/closed state). Optional — "
             "without it the held/forced anomaly detection is degraded.")
    company_id = fields.Many2one(
        "res.company", related="perimeter_id.company_id", store=True)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Each control point code must be unique per company.",
    )

    def action_pulse(self, seconds=None):
        """Convenience — pulse the magnet via the linked HTTP controller.
        Returns (ok, msg). Fail-secure: ако няма linked controller → deny."""
        self.ensure_one()
        if not self.controller_id:
            return False, "no HTTP controller linked"
        return self.controller_id.open(seconds=seconds)
