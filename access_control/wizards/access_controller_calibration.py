# -*- coding: utf-8 -*-
"""Auto-calibration wizard for access controller reader mapping.

Operator runs two walkthroughs:
  Route 1: e.g. clockwise (enter Door B, exit Door A)
  Route 2: reverse (enter Door A, exit Door B)

Wizard captures hr.rfid.event records between start/end timestamps
of each route and derives external_reader_id (entry) + internal_reader_id
(exit) per control point.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccessControllerCalibration(models.TransientModel):
    _name = "access.controller.calibration"
    _description = "Reader Mapping Calibration Wizard"

    name = fields.Char(default="Reader Calibration", required=True)

    state = fields.Selection([
        ("draft", "Setup"),
        ("route_1", "Recording Route 1"),
        ("route_1_done", "Route 1 captured"),
        ("route_2", "Recording Route 2"),
        ("route_2_done", "Route 2 captured"),
        ("applied", "Applied"),
    ], default="draft", required=True)

    controller_ids = fields.Many2many(
        "access.controller", required=True,
        domain=[("active", "=", True)],
        help="Controllers които ще калибрираш в тази обиколка.")
    card_id = fields.Many2one(
        "hr.rfid.card", string="Calibration Card",
        domain=[("active", "=", True)], required=True,
        help="Картата с която ще свайпваш по маршрута. Pick-нй "
             "съществуваща card master запис — wizard филтрира "
             "hr.rfid.event-те по нейния card_number.")
    card_number = fields.Char(
        related="card_id.card_number", readonly=True, store=False,
        help="Auto-derived от Calibration Card.")

    route_1_start = fields.Datetime(readonly=True)
    route_1_end = fields.Datetime(readonly=True)
    route_2_start = fields.Datetime(readonly=True)
    route_2_end = fields.Datetime(readonly=True)

    route_1_event_ids = fields.One2many(
        "access.controller.calibration.event", "wizard_id",
        domain=[("route", "=", "1")],
        readonly=True)
    route_2_event_ids = fields.One2many(
        "access.controller.calibration.event", "wizard_id",
        domain=[("route", "=", "2")],
        readonly=True)

    preview_html = fields.Html(readonly=True)

    # ── Actions ───────────────────────────────────────────────────────

    def action_start_route_1(self):
        self.ensure_one()
        self.route_1_start = fields.Datetime.now()
        self.route_1_end = False
        self.route_1_event_ids.unlink()
        self.state = "route_1"
        return self._reload_form()

    def action_stop_route_1(self):
        self.ensure_one()
        if not self.route_1_start:
            raise UserError(_("Start Route 1 first."))
        self.route_1_end = fields.Datetime.now()
        self._capture_events(route=1)
        self.state = "route_1_done"
        return self._reload_form()

    def action_start_route_2(self):
        self.ensure_one()
        self.route_2_start = fields.Datetime.now()
        self.route_2_end = False
        self.route_2_event_ids.unlink()
        self.state = "route_2"
        return self._reload_form()

    def action_stop_route_2(self):
        self.ensure_one()
        if not self.route_2_start:
            raise UserError(_("Start Route 2 first."))
        self.route_2_end = fields.Datetime.now()
        self._capture_events(route=2)
        self._compute_preview()
        self.state = "route_2_done"
        return self._reload_form()

    def action_apply(self):
        self.ensure_one()
        if self.state != "route_2_done":
            raise UserError(_("Complete both routes first."))
        applied = self._apply_mapping()
        self.state = "applied"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Calibration applied"),
                "message": _("Updated %s control point(s).", applied),
                "sticky": False,
                "next": self._reload_form(),
            },
        }

    def action_reset(self):
        self.ensure_one()
        (self.route_1_event_ids + self.route_2_event_ids).unlink()
        self.write({
            "state": "draft",
            "route_1_start": False, "route_1_end": False,
            "route_2_start": False, "route_2_end": False,
            "preview_html": False,
        })
        return self._reload_form()

    # ── Helpers ──────────────────────────────────────────────────────

    def _reload_form(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _capture_events(self, route):
        """Read hr.rfid.event records в прозореца на route-а."""
        self.ensure_one()
        start = self.route_1_start if route == 1 else self.route_2_start
        end = self.route_1_end if route == 1 else self.route_2_end
        if not start or not end:
            return
        ctrl_polimex_ids = [
            int(c.polimex_bus_id) for c in self.controller_ids
            if c.polimex_bus_id
        ]
        RfidEvent = self.env["hr.rfid.event"].sudo()
        domain = [
            ("event_ts", ">=", start),
            ("event_ts", "<=", end),
            ("event_type", "=", "card.read"),
            ("card_id", "=", (self.card_number or "").strip()),
        ]
        if ctrl_polimex_ids:
            domain.append(("ctrl_id", "in", ctrl_polimex_ids))
        events = RfidEvent.search(domain, order="event_ts asc")
        WizardEvent = self.env["access.controller.calibration.event"].sudo()
        for ev in events:
            controller = self.controller_ids.filtered(
                lambda c: c.polimex_bus_id == ev.ctrl_id)[:1]
            cp = self.env["access.control.point"].sudo().search([
                ("controller_id", "=", controller.id),
            ], limit=1) if controller else False
            WizardEvent.create({
                "wizard_id": self.id,
                "route": str(route),
                "ts": ev.event_ts,
                "ctrl_id": ev.ctrl_id,
                "reader_no": ev.reader_no,
                "controller_id": controller.id if controller else False,
                "control_point_id": cp.id if cp else False,
            })

    def _compute_preview(self):
        """Derive external/internal reader mapping per cp + show HTML."""
        self.ensure_one()
        mapping = self._derive_mapping()
        if not mapping:
            self.preview_html = _("<i>No events captured. Nothing to apply.</i>")
            return
        rows = []
        for cp_id, m in mapping.items():
            cp = self.env["access.control.point"].browse(cp_id)
            ext = m.get("external") or "—"
            int_r = m.get("internal") or "—"
            rows.append(
                f"<tr><td>{cp.display_name}</td>"
                f"<td>{ext}</td><td>{int_r}</td></tr>")
        self.preview_html = (
            "<h4>Derived Mapping</h4>"
            "<table class='table table-sm'>"
            "<thead><tr><th>Control Point</th>"
            "<th>External (entry)</th><th>Internal (exit)</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    def _derive_mapping(self):
        """Returns {cp_id: {"external": reader_no, "internal": reader_no}}.

        Logic:
        - Route 1 events sorted by ts: пръв event на cp X = entry (external),
          последен event на cp X = exit (internal).
        - Route 2 (reverse) попълва missing-те.
        """
        self.ensure_one()
        result = {}

        def absorb_route(events, role_first, role_last):
            """role_first: 'external' or 'internal'; role_last: opposite.
            Route 1 first swipe = entry, last = exit.
            Route 2 first swipe = entry too (just reversed door order),
            затова role_first stays 'external'."""
            if not events:
                return
            # First swipe of route → external (entry)
            first = events[0]
            if first.control_point_id and first.reader_no:
                cp_map = result.setdefault(first.control_point_id.id, {})
                cp_map.setdefault(role_first, str(first.reader_no))
            # Last swipe of route → internal (exit)
            last = events[-1]
            if last.control_point_id and last.reader_no:
                cp_map = result.setdefault(last.control_point_id.id, {})
                cp_map.setdefault(role_last, str(last.reader_no))

        absorb_route(self.route_1_event_ids, "external", "internal")
        absorb_route(self.route_2_event_ids, "external", "internal")
        return result

    def _apply_mapping(self):
        """Write external_reader_id / internal_reader_id on cp records."""
        self.ensure_one()
        mapping = self._derive_mapping()
        CP = self.env["access.control.point"].sudo()
        count = 0
        for cp_id, m in mapping.items():
            cp = CP.browse(cp_id)
            vals = {}
            if m.get("external"):
                vals["external_reader_id"] = m["external"]
            if m.get("internal"):
                vals["internal_reader_id"] = m["internal"]
            if vals:
                cp.write(vals)
                count += 1
        return count


class AccessControllerCalibrationEvent(models.TransientModel):
    _name = "access.controller.calibration.event"
    _description = "Reader Calibration Captured Event"
    _order = "ts asc"

    wizard_id = fields.Many2one(
        "access.controller.calibration", required=True, ondelete="cascade")
    route = fields.Selection(
        [("1", "Route 1"), ("2", "Route 2")], required=True)
    ts = fields.Datetime(readonly=True)
    ctrl_id = fields.Integer(string="Bus ID", readonly=True)
    reader_no = fields.Integer(string="Reader", readonly=True)
    controller_id = fields.Many2one(
        "access.controller", readonly=True)
    control_point_id = fields.Many2one(
        "access.control.point", readonly=True)
