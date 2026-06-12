# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
"""access_control bridge: Polimex push event → access.decision.flow.

Hooks в bus_inject's `_on_proxy_event` registry — обработва card.read
събития от Polimex push и предава ги на новия ZEN-driven decision flow
(паралелно със стария hr.rfid.event path в hr_aac).

Mapping:
- envelope.data.ctrl_id (Polimex controller bus_id) → access.controller
  чрез ново поле polimex_bus_id (extension)
- envelope.data.reader_no → external (1, 3, ...) / internal (2, 4, ...)
- envelope.data.card → access.credential through hr.rfid.card.card_number
"""

import logging

from odoo import _, api, fields, models

from .access_controller_time_schedule import (
    _TS_ALWAYS, _TS_MAX, _TS_MIN_ALLOC)

_logger = logging.getLogger(__name__)


class AccessControllerPolimex(models.Model):
    """Extension на legacy access.controller с Polimex-specific полета."""
    _inherit = "access.controller"

    polimex_bus_id = fields.Integer(
        string="Polimex Bus ID",
        help="RS-485 bus address of the physical Polimex controller "
             "(ctrl_id in push events). Used to route incoming events "
             "to the correct access.control.point.")
    polimex_convertor = fields.Integer(
        string="Polimex Web Module Serial",
        help="Serial of the Polimex Web Module (convertor field in "
             "heartbeat). Distinguishes physical Web Modules when there "
             "are >1 on a bus.")

    last_event_ts = fields.Datetime(
        string="Last Event",
        help="Timestamp of the last passage event through this controller. "
             "Updated by the proxy bridge.")

    time_schedule_ids = fields.One2many(
        "access.controller.time.schedule", "controller_id",
        string="Onboard Time Schedules",
        help="Polimex TS slots written into this controller (D3). Local "
             "cards reference these so windows are enforced offline.")

    def _ensure_time_schedule(self, schedule):
        """Return the onboard TS slot for `schedule` on this controller,
        allocating the next free ts_number if missing. `schedule` empty →
        the reserved 'always' slot (ts 1). Idempotent."""
        self.ensure_one()
        TS = self.env["access.controller.time.schedule"].sudo()
        if not schedule:
            slot = self.time_schedule_ids.filtered(
                lambda t: not t.schedule_id)
            if slot:
                return slot[0]
            return TS.create({"controller_id": self.id,
                              "ts_number": _TS_ALWAYS, "schedule_id": False})
        slot = self.time_schedule_ids.filtered(
            lambda t: t.schedule_id == schedule)
        if slot:
            return slot[0]
        used = set(self.time_schedule_ids.mapped("ts_number"))
        nxt = next((n for n in range(_TS_MIN_ALLOC, _TS_MAX + 1)
                    if n not in used), None)
        if nxt is None:
            from odoo.exceptions import UserError
            raise UserError(_(
                "Controller %s has no free Polimex TS slot (max %s).",
                self.display_name, _TS_MAX))
        return TS.create({"controller_id": self.id, "ts_number": nxt,
                          "schedule_id": schedule.id})


class AccessProxyBridge(models.AbstractModel):
    """Bus-inject hook: routes Polimex push events → decision flow.

    bus_inject controller looks for every model with _on_proxy_event
    method и го извиква с envelope. Тoзи AbstractModel няма таблица но
    се регистрира в registry.
    """
    _name = "access.proxy.bridge"
    _description = "Access Proxy Bridge (Polimex → ZEN decision)"

    @api.model
    def _on_proxy_event(self, envelope):
        """Entry point от bus_inject.

        envelope shape (per l10n_bg_erp_net_fp_bus_inject):
        {
          "v": 1, "type": "card.read", "id": "...", "ts": "...",
          "source": {"proxy": "erpnet-fp-mec", "device": "polimex-..."},
          "data": {
            "card": "0003201160", "event_n": 7, "ctrl_id": 38,
            "reader": 2, "convertor": 436900, "time": "20:36:53", ...
          }
        }
        """
        try:
            # Канonical key e `type` (bus_inject), не `event_type`.
            event_type = ((envelope or {}).get("type")
                          or (envelope or {}).get("event_type") or "")
            _logger.info(
                "access.proxy.bridge received: type=%s data keys=%s",
                event_type, list((envelope or {}).get("data", {}).keys()))
            # Inputs от Polimex които интересуват access flow:
            # - card.read/accept/denied — primary card swipe path
            # - door.sensor — door open/forced contact change
            # - button.pressed — exit button (REX) press
            if event_type not in (
                    "card.read", "card.accept", "card.denied",
                    "door.sensor", "button.pressed"):
                return  # other events (heartbeat/online/controller.*) skipped
            data = (envelope or {}).get("data", {})
            card_num = data.get("card")
            ctrl_id = data.get("ctrl_id") or data.get("id")
            reader_no = data.get("reader") or data.get("reader_no")
            if not card_num or not ctrl_id:
                _logger.debug(
                    "access_proxy_bridge: skip — missing card/ctrl_id (%s)",
                    data)
                return

            # 1. Resolve controller by Polimex bus_id
            Ctrl = self.env["access.controller"].sudo()
            controller = Ctrl.search([
                ("polimex_bus_id", "=", int(ctrl_id)),
                ("active", "=", True),
            ], limit=1)
            if not controller:
                _logger.info(
                    "access_proxy_bridge: no access.controller с "
                    "polimex_bus_id=%s — skipping (probably hr_aac-only setup)",
                    ctrl_id)
                return

            # 2. Resolve control point — match по reader_no към
            # external_reader_id (entry) или internal_reader_id (exit)
            # за да диференцираме между doors на multi-door controllers
            # (iCON130 = 2 doors × 2 readers, iCON180 = 4 doors).
            CP = self.env["access.control.point"].sudo()
            reader_str = str(reader_no) if reader_no else False
            control_point = False
            if reader_str:
                control_point = CP.search([
                    ("controller_id", "=", controller.id),
                    ("active", "=", True),
                    "|",
                    ("external_reader_id", "=", reader_str),
                    ("internal_reader_id", "=", reader_str),
                ], limit=1)
            if not control_point:
                # Fallback на първия cp (когато reader_id-та не са
                # configured — single-door controllers).
                control_point = CP.search([
                    ("controller_id", "=", controller.id),
                    ("active", "=", True),
                ], limit=1)
            if not control_point:
                _logger.warning(
                    "access_proxy_bridge: controller %s няма linked "
                    "control point — skipping decision flow", controller.name)
                return

            # 3. Resolve credential via hr.rfid.card.card_number
            Card = self.env["hr.rfid.card"].sudo()
            card = Card.search([("card_number", "=", card_num)], limit=1)
            credential = card.credential_id if card else False

            # 4. Build signal matrix
            signal_matrix = self._build_signal_matrix(
                event_type, data, control_point, reader_no)

            # 5. Run decision flow
            ts = self._parse_ts(data)
            flow = self.env["access.decision.flow"]
            event = flow.evaluate_passage(
                control_point, credential, signal_matrix, ts=ts)
            controller.sudo().write({"last_event_ts": ts or fields.Datetime.now()})
            _logger.info(
                "access_proxy_bridge: passage event %s @ %s — direction=%s "
                "anomaly=%s result=%s",
                event.id, control_point.code, event.direction,
                event.anomaly_hint, event.result)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "access_proxy_bridge: failed processing envelope %s", envelope)

    def _build_signal_matrix(self, event_type, data, control_point, reader_no):
        """Map Polimex event shape to abstract signal matrix.

        Polimex event_n vocabulary (per FA/F0 opcodes):
        - card.read accepted → external/internal reader 'fire' + magnet
          'open' + door 'opened'
        - card.read denied   → reader 'denied'
        """
        sm = {
            "external_reader": None,
            "internal_reader": None,
            "magnet": None,
            "door": None,
        }
        is_denied = (event_type == "card.denied" or
                     str(data.get("err", "0")) != "0")
        signal = "denied" if is_denied else "fire"

        # Reader 1/3 → external; 2/4 → internal — mapping за iCON130
        # (двойни врати); iCON115 typically use 1=internal/2=external
        # depending on wiring. Read от control point definition.
        try:
            reader_no = int(reader_no) if reader_no is not None else 0
        except (TypeError, ValueError):
            reader_no = 0

        # Priority: ако cp.external_reader_id/internal_reader_id са set,
        # тяхният config е source-of-truth (wiring varies per install).
        # Fallback на heuristic (odd=external) само когато cp няма
        # explicit mapping.
        ext_id = (control_point.external_reader_id or "").strip()
        int_id = (control_point.internal_reader_id or "").strip()
        reader_str = str(reader_no)
        if ext_id or int_id:
            # Explicit cp config — use it strictly, no heuristic fallback
            if ext_id and ext_id == reader_str:
                sm["external_reader"] = signal
            elif int_id and int_id == reader_str:
                sm["internal_reader"] = signal
        else:
            # No cp config → heuristic fallback (1,3=external; 2,4=internal)
            if reader_no in (1, 3):
                sm["external_reader"] = signal
            elif reader_no in (2, 4):
                sm["internal_reader"] = signal

        if not is_denied:
            sm["magnet"] = "open"
            sm["door"] = "opened"
        return sm

    def _parse_ts(self, data):
        """Polimex event има date 'MM.DD.YY' + time 'HH:MM:SS' OR ISO ts.

        КРИТИЧНО: Odoo Datetime fields винаги storage в UTC. Полимекс
        controllers shлат timestamps в LOCAL TIME (Europe/Sofia) без
        tz info. Ако ги парснем като naive → Odoo ги пише като UTC →
        passage events ще са с +3h drift.

        Strategy:
        - tz-aware ISO → astimezone UTC → strip tzinfo
        - naive ISO или Polimex date/time → assume Sofia local, convert
          към UTC чрез company.partner.tz (fallback Europe/Sofia)
        """
        from datetime import datetime
        import pytz
        company_tz = (self.env.company.partner_id.tz
                      or "Europe/Sofia")
        local_tz = pytz.timezone(company_tz)

        def to_utc_naive(dt):
            if dt.tzinfo is None:
                # Assume local
                dt = local_tz.localize(dt)
            return dt.astimezone(pytz.utc).replace(tzinfo=None)

        ts = data.get("ts") or data.get("event_ts")
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                return to_utc_naive(dt)
            except (TypeError, ValueError):
                pass
        d = data.get("date")
        t = data.get("time")
        if d and t:
            try:
                mm, dd, yy = d.split(".")
                yy_full = 2000 + int(yy) if int(yy) < 100 else int(yy)
                dt = datetime.strptime(
                    f"{yy_full:04d}-{int(mm):02d}-{int(dd):02d} {t}",
                    "%Y-%m-%d %H:%M:%S")
                return to_utc_naive(dt)
            except (TypeError, ValueError):
                pass
        return fields.Datetime.now()
