# -*- coding: utf-8 -*-
"""Auto-calibration wizard for access controller reader mapping.

Single-walk approach:
  Operator declares starting position (inside / outside) + makes ONE
  walk through всички врати на калибрираните controllers. Wizard
  alternating-state derive-ва кой reader е external (entry — flip-вa
  state inside-ward) vs internal (exit — flip-ва outside-ward).

Works for:
  * Single-door controller (iCON115): 2 swipes — exit + entry —
    populate-ват двете reader_id-та на единствения cp.
  * Multi-door perimeter (iCON130 — 2 врати): 2 swipes — entry през
    Door A → exit през Door B (или обратно). Wizard razмеря кой
    cp е external/internal на всеки door.
  * Многомерни sequences (>2 врати): alternating logic — state flip-ва
    на всеки swipe; non-perimeter switches трябва да са valid (Building
    Entry → Office Area например изисква 2 separate flips).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccessControllerCalibration(models.TransientModel):
    _name = "access.controller.calibration"
    _description = "Reader Mapping Calibration Wizard"

    name = fields.Char(default="Reader Calibration", required=True)

    state = fields.Selection([
        ("draft", "Setup"),
        ("walking", "Recording Walk"),
        ("walking_done", "Walk Captured"),
        ("applied", "Applied"),
    ], default="draft", required=True)

    controller_ids = fields.Many2many(
        "access.controller", required=True,
        domain=[("active", "=", True)],
        help="Controllers които ще калибрираш в тази обиколка.")
    card_id = fields.Many2one(
        "hr.rfid.card", string="Calibration Card",
        domain=[("active", "=", True)], required=True,
        help="Картата с която ще свайпваш. Pick-нй съществуваща card "
             "master запис — wizard филтрира hr.rfid.event-те по нея.")
    card_number = fields.Char(
        related="card_id.card_number", readonly=True, store=False)
    starting_position = fields.Selection([
        ("inside", "🏠 Inside (вътре в perimeter-а)"),
        ("outside", "🚪 Outside (вън от perimeter-а)"),
    ], required=True, default="inside",
        help="Къде си преди да започнеш обиколя. При single door: "
             "inside=първият swipe ще е exit; outside=първият ще е entry.")

    walk_start = fields.Datetime(readonly=True)
    walk_end = fields.Datetime(readonly=True)

    plan_step_ids = fields.One2many(
        "access.controller.calibration.step", "wizard_id",
        string="Walk Plan",
        help="Pre-declared последователност: коя врата с каква роля. "
             "Bутон 'Generate Plan' auto-populate-ва от controllers.")
    walk_event_ids = fields.One2many(
        "access.controller.calibration.event", "wizard_id",
        readonly=True)

    preview_html = fields.Html(readonly=True)

    # ── Actions ───────────────────────────────────────────────────────

    def action_generate_plan(self):
        """Auto-populate plan_step_ids: за всеки cp на избраните controllers,
        генерирай 2 steps (entry + exit) според starting_position.

        Default order: ако start=inside → first step е 'exit', after е 'entry'
        (за same cp ако single-door, или alternating ако multi-door).
        Operator може да reorder/edit / delete steps."""
        self.ensure_one()
        if not self.controller_ids:
            raise UserError(_("Pick controllers first."))
        self.plan_step_ids.unlink()
        Step = self.env["access.controller.calibration.step"].sudo()
        CP = self.env["access.control.point"].sudo()
        cps = CP.search([
            ("controller_id", "in", self.controller_ids.ids),
            ("active", "=", True),
        ], order="controller_id, name")
        seq = 10
        state = self.starting_position
        for cp in cps:
            # First role зависи от текущо state
            role = "exit" if state == "inside" else "entry"
            Step.create({
                "wizard_id": self.id,
                "sequence": seq,
                "control_point_id": cp.id,
                "role": role,
            })
            seq += 10
            # Flip state — следващ step (return) става opposite role на същия cp
            state = "outside" if state == "inside" else "inside"
            Step.create({
                "wizard_id": self.id,
                "sequence": seq,
                "control_point_id": cp.id,
                "role": "exit" if state == "inside" else "entry",
            })
            seq += 10
            state = "outside" if state == "inside" else "inside"
        return self._reload_form()

    def action_start_walk(self):
        self.ensure_one()
        self.walk_start = fields.Datetime.now()
        self.walk_end = False
        self.walk_event_ids.unlink()
        self.preview_html = False
        self.state = "walking"
        return self._reload_form()

    def action_stop_walk(self):
        self.ensure_one()
        if not self.walk_start:
            raise UserError(_("Start the walk first."))
        self.walk_end = fields.Datetime.now()
        self._capture_events()
        if not self.walk_event_ids:
            raise UserError(_(
                "No card.read events recorded for card %s between %s "
                "and %s. Махнй wizard-а и swipe-вай отново.",
                self.card_number, self.walk_start, self.walk_end))
        self._compute_preview()
        self.state = "walking_done"
        return self._reload_form()

    def action_apply(self):
        self.ensure_one()
        if self.state != "walking_done":
            raise UserError(_("Capture a walk first."))
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
        self.walk_event_ids.unlink()
        self.write({
            "state": "draft",
            "walk_start": False, "walk_end": False,
            "preview_html": False,
        })
        return self._reload_form()

    # ── Helpers ───────────────────────────────────────────────────────

    def _reload_form(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _capture_events(self):
        """Read hr.rfid.event records в прозореца на walk-а."""
        self.ensure_one()
        if not self.walk_start or not self.walk_end:
            return
        ctrl_polimex_ids = [
            int(c.polimex_bus_id) for c in self.controller_ids
            if c.polimex_bus_id
        ]
        RfidEvent = self.env["hr.rfid.event"].sudo()
        domain = [
            ("event_ts", ">=", self.walk_start),
            ("event_ts", "<=", self.walk_end),
            ("event_type", "=", "card.read"),
            ("card_id", "=", (self.card_number or "").strip()),
        ]
        if ctrl_polimex_ids:
            domain.append(("ctrl_id", "in", ctrl_polimex_ids))
        events = RfidEvent.search(domain, order="event_ts asc")
        WizardEvent = self.env["access.controller.calibration.event"].sudo()
        CP = self.env["access.control.point"].sudo()
        for idx, ev in enumerate(events, start=1):
            controller = self.controller_ids.filtered(
                lambda c: c.polimex_bus_id == ev.ctrl_id)[:1]
            cp = CP.search([
                ("controller_id", "=", controller.id),
            ], limit=1) if controller else False
            WizardEvent.create({
                "wizard_id": self.id,
                "sequence": idx,
                "ts": ev.event_ts,
                "ctrl_id": ev.ctrl_id,
                "reader_no": ev.reader_no,
                "controller_id": controller.id if controller else False,
                "control_point_id": cp.id if cp else False,
            })

    def _derive_mapping(self):
        """Two modes:

        A) Plan-driven (plan_step_ids set): pair-вай i-тия event с
           i-тия step. step.role диктува дали event.reader_no става
           external_reader_id (entry) или internal_reader_id (exit).
           По-надежден за >2 врати и multi-perimeter sequences.

        B) Auto alternating (no plan): state = starting_position;
           всеки event flip-ва state. Inside→outside = exit (internal);
           outside→inside = entry (external).

        Returns: {cp_id: {"external": reader_no, "internal": reader_no}}
        """
        self.ensure_one()
        result = {}
        events = self.walk_event_ids.sorted("sequence")
        steps = self.plan_step_ids.sorted("sequence")
        if steps:
            for i, ev in enumerate(events):
                if i >= len(steps):
                    break
                step = steps[i]
                cp_id = (step.control_point_id.id
                         or (ev.control_point_id and ev.control_point_id.id))
                if not cp_id or not ev.reader_no:
                    continue
                cp_map = result.setdefault(cp_id, {})
                if step.role == "entry":
                    cp_map.setdefault("external", str(ev.reader_no))
                    ev.inferred_role = "entry"
                else:
                    cp_map.setdefault("internal", str(ev.reader_no))
                    ev.inferred_role = "exit"
                step.matched_event_id = ev.id
        else:
            state = self.starting_position
            for ev in events:
                if not ev.control_point_id or not ev.reader_no:
                    continue
                cp_id = ev.control_point_id.id
                cp_map = result.setdefault(cp_id, {})
                if state == "inside":
                    cp_map.setdefault("internal", str(ev.reader_no))
                    ev.inferred_role = "exit"
                    state = "outside"
                else:
                    cp_map.setdefault("external", str(ev.reader_no))
                    ev.inferred_role = "entry"
                    state = "inside"
        return result

    def _compute_preview(self):
        self.ensure_one()
        mapping = self._derive_mapping()
        if not mapping:
            self.preview_html = _("<i>No events captured.</i>")
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
            f"<h4>Derived Mapping (start: {self.starting_position})</h4>"
            "<table class='table table-sm'>"
            "<thead><tr><th>Control Point</th>"
            "<th>External (entry)</th><th>Internal (exit)</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    def _apply_mapping(self):
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


class AccessControllerCalibrationStep(models.TransientModel):
    """Pre-declared plan step: коя врата + каква роля."""
    _name = "access.controller.calibration.step"
    _description = "Reader Calibration Plan Step"
    _order = "sequence asc"

    wizard_id = fields.Many2one(
        "access.controller.calibration", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    control_point_id = fields.Many2one(
        "access.control.point", required=True,
        help="Коя врата ще се мине на тая стъпка.")
    role = fields.Selection([
        ("entry", "🚪→ Entry (от outside към inside)"),
        ("exit", "→🚪 Exit (от inside към outside)"),
    ], required=True, default="entry",
        help="Каква е стъпката — entry (external reader) или "
             "exit (internal reader).")
    matched_event_id = fields.Many2one(
        "access.controller.calibration.event",
        readonly=True,
        help="Captured event match-нат с този step (по sequence).")


class AccessControllerCalibrationEvent(models.TransientModel):
    _name = "access.controller.calibration.event"
    _description = "Reader Calibration Captured Event"
    _order = "sequence asc, ts asc"

    wizard_id = fields.Many2one(
        "access.controller.calibration", required=True, ondelete="cascade")
    sequence = fields.Integer()
    ts = fields.Datetime(readonly=True)
    ctrl_id = fields.Integer(string="Bus ID", readonly=True)
    reader_no = fields.Integer(string="Reader", readonly=True)
    controller_id = fields.Many2one(
        "access.controller", readonly=True)
    control_point_id = fields.Many2one(
        "access.control.point", readonly=True)
    inferred_role = fields.Selection([
        ("entry", "Entry (external)"),
        ("exit", "Exit (internal)"),
    ], readonly=True)
