# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""access.context.builder — 3-dim context + decision flow.

Hybrid arch (Open Q#4, agent анализ 2026-05-26):
- Python helper `_derive_direction(matrix, prev_event)` за sequence+timing
  patterns които ZEN/JDM stateless не може
- ZEN graph (А1–A3) консумира `direction` + `anomaly_hint` като context
  fields за business decisions

Същият `_derive_direction` логика се deploy-ва байт-идентично в proxy
(Phase 3) — версионира се през heartbeat.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Window in seconds:
#   _TAILGATE_WINDOW_SEC — двойно swipе в твърде кратко време = tailgating
#   _PREV_EVENT_WINDOW_SEC — search window за prev event на perimeter
#       (за exit_without_entry derivation). Трябва ≥ workday за да
#       allow check-in сутрин → check-out вечерта. 12h по подразбиране.
_TAILGATE_WINDOW_SEC = 3
_PREV_EVENT_WINDOW_SEC = 43200  # 12 hours
_HELD_THRESHOLD_SEC = 30


class AccessContextBuilder(models.AbstractModel):
    """Stateless service за изграждане на ZEN context dict от
    физически inputs. AbstractModel — не persistent, но регистриран
    в env за лесна разширяемост от downstream модули.
    """
    _name = "access.context.builder"
    _description = "Access Context Builder (3-dim + direction derive)"

    @api.model
    def build_context(self, control_point, credential, signal_matrix, ts=None):
        """Main entry point. Returns dict готов за ZEN evaluate."""
        ts = ts or fields.Datetime.now()
        prev_event = self._last_event_for_point(
            control_point, ts, credential=credential)
        direction, anomaly_hint = self._derive_direction(
            signal_matrix, prev_event, credential)
        perimeter = control_point.perimeter_id
        chain = perimeter._perimeter_chain() if perimeter else []
        parent_present = self._check_parent_occupancy(
            credential.subject_id, perimeter) if perimeter else False
        within_window, window = self._resolve_window(perimeter, ts)
        return {
            # Физическо
            "signal": dict(signal_matrix or {}),
            "direction": direction,
            "anomaly_hint": anomaly_hint,
            # Пространствено
            "perimeter_id": perimeter.id if perimeter else False,
            "perimeter_code": perimeter.code if perimeter else False,
            "perimeter_chain_codes": [p.code for p in chain],
            "requires_parent_presence": (perimeter.requires_parent_presence
                                          if perimeter else False),
            "parent_present": parent_present,
            "enforcement": perimeter.enforcement if perimeter else "soft",
            # Темпорално
            "ts": ts.isoformat() if ts else None,
            "within_window": within_window,
            "window": window,
            "tolerance_minutes": (perimeter.tolerance_minutes
                                   if perimeter else 0),
            # Credential
            "credential_id": credential.id if credential else False,
            "credential_kind": (credential.credential_kind
                                if credential else None),
            "credential_active": self._credential_valid_at(credential, ts),
            "subject_id": (credential.subject_id.id
                           if credential and credential.subject_id else False),
        }

    # ── Credential validity ─────────────────────────────────────────
    @api.model
    def _credential_valid_at(self, credential, ts):
        if not credential or not credential.active:
            return False
        if credential.valid_from and credential.valid_from > ts:
            return False
        if credential.valid_to and credential.valid_to < ts:
            return False
        return True

    # ── Stateful preprocessing (Python only — JDM не може) ──────────
    @api.model
    def _last_event_for_point(self, control_point, ts, credential=None):
        """Search the most recent passage event на ниво PERIMETER
        (всички control points в zone-та) за дадения credential. Multi-
        door perimeter (напр. 2 врати на офис): влизане през Door A,
        излизане през Door B → същата зона; prev_event трябва да се
        намери дори да е на различна врата.

        Fallback на same control_point ако perimeter не е set."""
        cutoff = ts - timedelta(seconds=_PREV_EVENT_WINDOW_SEC)
        Event = self.env["access.passage.event"].sudo()
        domain = [
            ("ts", ">=", cutoff),
            ("ts", "<", ts),
        ]
        if control_point.perimeter_id:
            domain.append(
                ("perimeter_id", "=", control_point.perimeter_id.id))
        else:
            domain.append(("control_point_id", "=", control_point.id))
        if credential:
            domain.append(("credential_id", "=", credential.id))
        return Event.search(domain, order="ts desc", limit=1)

    @api.model
    def _derive_direction(self, signal_matrix, prev_event, credential):
        """Pure-Python — определя direction + anomaly от signal matrix
        и предходно събитие. Тества се table-driven.

        Returns: (direction: 'in'|'out'|None, anomaly_hint: str|None)

        Patterns (от спека):
        - ext fires + magnet open + door open    → ('in', None)
        - int fires + magnet open + door open    → ('out', None)
        - magnet break без reader pulse           → (None, 'forced')
        - ext fires + prev_in за същата карта <3s → ('in', 'tailgating')
        - int fires без предходен external        → (None, 'exit_without_entry')
        - ext denied + door opened                → ('in', 'denied_but_opened')
        - magnet open > held threshold            → (None, 'held')

        ⚠️ Този helper трябва да живее БАЙТ-ИДЕНТИЧЕН в proxy
        (Phase 3: Odoo.ErpNet.FP/proxy/access/context_builder.py).
        Версия се pin-ва към ZEN graph version в heartbeat payload.
        """
        sm = signal_matrix or {}
        ext = sm.get("external_reader") or sm.get("ext")
        int_r = sm.get("internal_reader") or sm.get("int")
        magnet = sm.get("magnet")
        door = sm.get("door")

        # Edge: held door
        if magnet == "open_too_long":
            return (None, "held")

        # Edge: forced — magnet broken без reader pulse
        if magnet == "break" and not ext and not int_r:
            return (None, "forced")

        # Denied but opened — external denied AND door opened
        if ext == "denied" and door == "opened":
            return ("in", "denied_but_opened")

        # Normal in: ext fire + magnet open + door open
        if ext in ("fire", "accept") and magnet in ("open", "released") \
                and door in ("opened", None):
            # Tailgating check: предходно "in" same credential <3s
            if prev_event and prev_event.direction == "in" \
                    and credential and prev_event.credential_id == credential \
                    and (prev_event.ts and prev_event.ts > (
                        fields.Datetime.now() - timedelta(
                            seconds=_TAILGATE_WINDOW_SEC))):
                return ("in", "tailgating")
            return ("in", None)

        # Normal out: int fire + magnet open + door open
        if int_r in ("fire", "accept") and magnet in ("open", "released") \
                and door in ("opened", None):
            # Exit without entry: int fires но няма prev external event
            if not prev_event or prev_event.direction != "in":
                return (None, "exit_without_entry")
            return ("out", None)

        # Fallback: не може да определи
        return (None, None)

    # ── Spatial dimension helpers ────────────────────────────────────
    @api.model
    def _check_parent_occupancy(self, subject, perimeter):
        if not subject or not perimeter or not perimeter.parent_id:
            return False
        Occupancy = self.env["access.occupancy"].sudo()
        rec = Occupancy.search([
            ("subject_id", "=", subject.id),
            ("perimeter_id", "=", perimeter.parent_id.id),
        ], limit=1)
        return rec.state == "inside" if rec else False

    # ── Temporal dimension ───────────────────────────────────────────
    @api.model
    def _resolve_window(self, perimeter, ts):
        """Returns (within_window: bool, window: dict|None)."""
        if not perimeter or not perimeter.calendar_id:
            return (True, None)  # 24/7
        # TODO: full resource.calendar integration в следваща итерация.
        # Placeholder: винаги within window. Tolerance logic в ZEN graph.
        return (True, {"calendar_id": perimeter.calendar_id.id})


class AccessDecisionFlow(models.AbstractModel):
    """High-level decision orchestrator. Build context → ZEN evaluate
    → log → side effects (passage event, violation, occupancy)."""
    _name = "access.decision.flow"
    _description = "Access Decision Flow (orchestrator)"

    @api.model
    def evaluate_passage(self, control_point, credential, signal_matrix,
                         ts=None):
        """Single entry point за passage decision. Returns the created
        access.passage.event record."""
        ts = ts or fields.Datetime.now()
        Builder = self.env["access.context.builder"]
        context = Builder.build_context(
            control_point, credential, signal_matrix, ts=ts)

        # Locate ZEN table — perimeter-specific override или default
        ZenTable = self.env["zen.decision.table"]
        zen_table = control_point.perimeter_id.zen_table_id \
            or ZenTable.get_active("access_default",
                                    company_id=control_point.company_id.id)
        evaluation = zen_table.evaluate(context, trace=True)
        result_out = evaluation["result"]
        zen_log = zen_table.log(context, result_out,
                                 trace=evaluation.get("trace"),
                                 executed_in="odoo")

        # Resolve final action — ZEN result може да върне:
        #  {"action": "accept"|"deny", "violation_type": "...", "priority": "..."}
        action = (result_out or {}).get("action", "deny")
        anomaly = context.get("anomaly_hint")
        violation_type = (result_out or {}).get("violation_type") or anomaly
        priority = (result_out or {}).get("priority", "medium")

        # Soft enforcement — fail-safe изход
        perimeter = control_point.perimeter_id
        if perimeter and perimeter.enforcement == "soft" \
                and context.get("direction") == "out" \
                and action == "deny":
            # Fail-safe: пусни изхода, отбележи violation
            action = "accept"
            violation_type = violation_type or "soft_exit_override"

        # Determine event result
        if action == "accept" and not anomaly:
            event_result = "accept"
        elif action == "accept" and anomaly:
            event_result = "violation"  # passed but anomaly
        else:
            event_result = "deny" if not anomaly else "violation"

        # Append passage.event
        Event = self.env["access.passage.event"].sudo()
        event = Event.create({
            "control_point_id": control_point.id,
            "credential_id": credential.id if credential else False,
            "ts": ts,
            "direction": context.get("direction"),
            "anomaly_hint": anomaly,
            "result": event_result,
            "signal_matrix": signal_matrix,
            "context_in": context,
            "result_out": result_out,
            "zen_log_id": zen_log.id,
        })

        # Violation record ако нужно
        if event_result == "violation" or violation_type:
            self.env["access.violation"].sudo().create({
                "event_id": event.id,
                "violation_type": violation_type or "other",
                "priority": priority,
                "hr_review_state": "pending"
                    if priority in ("high", "critical") else "none",
            })

        # Occupancy update (само ако accept + direction known)
        if event_result in ("accept", "violation") \
                and credential and credential.subject_id \
                and perimeter and context.get("direction"):
            self.env["access.occupancy"].sudo().upsert(
                subject_id=credential.subject_id.id,
                perimeter_id=perimeter.id,
                direction=context.get("direction"),
                event_id=event.id,
                ts=ts,
            )

        # Per-perimeter attendance log (TZ-aware) — open/close записи
        if event_result in ("accept", "violation") \
                and credential and credential.subject_id and perimeter:
            AttLog = self.env["access.attendance.log"].sudo()
            direction = context.get("direction")
            if direction == "in":
                AttLog.open_entry(credential.subject_id, perimeter,
                                   event, ts=ts)
            elif direction == "out":
                AttLog.close_exit(credential.subject_id, perimeter,
                                   event, ts=ts)

        # Pulse the magnet ако accept
        if event_result == "accept" and control_point.controller_id:
            control_point.action_pulse()

        return event
