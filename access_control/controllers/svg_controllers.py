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
"""HTTP routes за serve на динамично-генерирани SVG визуализации.

- /access_control/svg/direction/<event_id>     → single passage event arrow
- /access_control/svg/heatmap/<perimeter_id>   → 24h × 7d temporal heatmap
- /access_control/svg/site/<facility_id>        → floor plan с live devices
"""

from datetime import datetime, timedelta

from odoo import http
from odoo.http import request

from ..svg import (direction_arrow, heatmap_24h_7d, site_map_with_devices,
                   trail_chain)


_HEADERS_SVG = [
    ("Content-Type", "image/svg+xml; charset=utf-8"),
    ("Cache-Control", "no-cache, no-store, must-revalidate"),
    ("Pragma", "no-cache"),
]


class AccessControlSvg(http.Controller):

    @http.route("/access_control/svg/direction/<int:event_id>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def svg_direction(self, event_id, **kw):
        event = request.env["access.passage.event"].browse(event_id)
        try:
            event.check_access("read")
        except Exception:
            return request.not_found()
        svg = direction_arrow(event.direction, event.anomaly_hint)
        return request.make_response(svg, headers=_HEADERS_SVG)

    @http.route("/access_control/svg/heatmap/<int:perimeter_id>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def svg_heatmap(self, perimeter_id, days=30, **kw):
        perimeter = request.env["access.perimeter"].browse(perimeter_id)
        try:
            perimeter.check_access("read")
        except Exception:
            return request.not_found()
        # Aggregate passage events for last N days
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        since = datetime.utcnow() - timedelta(days=days)
        Event = request.env["access.passage.event"].sudo()
        events = Event.search([
            ("perimeter_id", "=", perimeter_id),
            ("ts", ">=", since),
        ])
        buckets = [0] * 168
        for e in events:
            if not e.ts:
                continue
            # Python weekday() Mon=0..Sun=6 — same като индексите ни
            idx = e.ts.weekday() * 24 + e.ts.hour
            buckets[idx] += 1
        title = f"{perimeter.name} · last {days} days · {sum(buckets)} passages"
        svg = heatmap_24h_7d(buckets, title=title)
        return request.make_response(svg, headers=_HEADERS_SVG)

    @http.route("/access_control/svg/site/<int:facility_id>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def svg_site(self, facility_id, floor_id=None, **kw):
        """Floor plan на facility (или конкретен floor) с overlay
        на device placements + live state на access points."""
        try:
            facility = request.env["access.facility"].browse(facility_id)
            facility.check_access("read")
        except Exception:
            return request.not_found()

        Placement = request.env["access.device_placement"].sudo()
        AccessPoint = request.env["access.access_point"].sudo()
        Occupancy = request.env["access.occupancy"].sudo()

        p_domain = [("facility_id", "=", facility_id)]
        ap_domain = [("facility_id", "=", facility_id)]
        if floor_id:
            try:
                floor_id = int(floor_id)
            except (TypeError, ValueError):
                floor_id = None
            if floor_id:
                p_domain.append(("floor_id", "=", floor_id))
                ap_domain.append(("floor_id", "=", floor_id))

        placements_data = []
        for p in Placement.search(p_domain):
            placements_data.append({
                "id": p.id,
                "name": p.name or "",
                "device_kind": p.device_kind or "other",
                "nx": p.position_nx or 0.5,
                "ny": p.position_ny or 0.5,
                "bearing_degrees": p.bearing_degrees or 0,
                "fov_degrees": p.fov_degrees or 0,
                "range_meters": p.range_meters or 0,
                "status_color": p.status_color or "",
            })

        access_points_data = []
        for ap in AccessPoint.search(ap_domain):
            # Derive live_state от recent activity на свързания controller
            live_state = self._derive_ap_live_state(ap)
            access_points_data.append({
                "id": ap.id,
                "name": ap.name or "",
                "point_type": ap.point_type or "",
                "nx": ap.position_nx or 0.5,
                "ny": ap.position_ny or 0.5,
                "live_state": live_state,
            })

        # Optional background image from facility (ако модулът има image поле)
        bg_url = None
        if hasattr(facility, "image_floor_plan") and facility.image_floor_plan:
            bg_url = f"/web/image/access.facility/{facility.id}/image_floor_plan"

        svg = site_map_with_devices(
            facility.name or "Facility",
            placements_data, access_points_data,
            background_url=bg_url,
        )
        return request.make_response(svg, headers=_HEADERS_SVG)

    def _derive_ap_live_state(self, access_point):
        """Look at recent (last 30s) passage event през controller-а на
        тoзи access point. Returns: 'idle' | 'in' | 'out' | 'anomaly'."""
        if not access_point.controller_id:
            return "idle"
        # access.access_point → access.controller. access.control.point
        # имa controller_id също — search-ваме control_point-ите за тoзи
        # controller, после recent events.
        CP = request.env["access.control.point"].sudo()
        cps = CP.search([("controller_id", "=", access_point.controller_id.id)])
        if not cps:
            return "idle"
        Event = request.env["access.passage.event"].sudo()
        since = datetime.utcnow() - timedelta(seconds=30)
        recent = Event.search([
            ("control_point_id", "in", cps.ids),
            ("ts", ">=", since),
        ], order="ts desc", limit=1)
        if not recent:
            return "idle"
        if recent.anomaly_hint or recent.result == "violation":
            return "anomaly"
        if recent.direction == "in":
            return "in"
        if recent.direction == "out":
            return "out"
        return "idle"


class AccessControlTrailSvg(http.Controller):
    """Daily trail visualization за employee."""

    @http.route("/access_control/svg/trail/employee/<int:employee_id>",
                type="http", auth="user", methods=["GET"], csrf=False)
    def svg_trail_employee(self, employee_id, date=None, **kw):
        """Renders horizontal chain SVG за passage events на даден
        employee + дата (YYYY-MM-DD; default = today)."""
        emp = request.env["hr.employee"].browse(employee_id)
        try:
            emp.check_access("read")
        except Exception:
            return request.not_found()
        try:
            day = (datetime.strptime(date, "%Y-%m-%d").date()
                   if date else datetime.utcnow().date())
        except ValueError:
            day = datetime.utcnow().date()
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        events = request.env["access.passage.event"].search([
            ("employee_id", "=", emp.id),
            ("ts", ">=", start),
            ("ts", "<", end),
        ], order="ts asc")
        payload = []
        for e in events:
            payload.append({
                "ts": e.ts.strftime("%H:%M") if e.ts else "",
                "cp": e.control_point_id.name or "?",
                "dir": e.direction,
                "perimeter": e.perimeter_id.name or "",
                "color": "#3498DB",
                "anomaly": e.anomaly_hint,
                "slot": e.time_slot_id.name or "",
                "slot_color": e.time_slot_id.color or "#7F8C8D",
            })
        label = f"{emp.name} — {day.isoformat()}"
        svg = trail_chain(payload, day_label=label)
        return request.make_response(svg, headers=_HEADERS_SVG)
