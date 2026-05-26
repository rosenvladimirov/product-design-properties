# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Pure-Python SVG renderers за access_control визуализации.

Без external libraries (matplotlib/svgwrite/etc.) — генерира raw SVG
strings. По-малък container footprint + детерминистичен output (важно
за caching).

3 рендера:
- direction_arrow(direction, anomaly_hint) → малък 64×64 SVG icon
  за passage event (зелен=in, жълт=out, червен=anomaly).
- heatmap_24h_7d(buckets) → 24h × 7d temporal heatmap (color
  intensity = passage count).
- site_map_with_devices(facility, placements, states) → floorplan
  overlay с devices в нормализирани coords + live state coloring.
"""

from __future__ import annotations

from xml.sax.saxutils import escape


# ── Цветова палитра ──────────────────────────────────────────────────
_PALETTE = {
    "in": "#27AE60",          # зелено
    "out": "#F39C12",         # оранжево
    "anomaly": "#C0392B",     # червено
    "neutral": "#7F8C8D",     # сив
    "magnet": "#8E44AD",      # лилав (актуатор)
    "reader": "#3498DB",      # синьо (вход)
    "camera": "#2C3E50",      # тъмно сиво
    "biometric": "#16A085",   # тюркоаз
    "bg": "#FAFBFC",
    "grid": "#E5E9EC",
    "text": "#2C3E50",
}

_ANOMALY_GLYPHS = {
    "forced": "⚠",
    "held": "⏱",
    "tailgating": "≫",
    "exit_without_entry": "⤴",
    "denied_but_opened": "✗",
}


def _svg_header(w: int, h: int, viewbox: str | None = None) -> str:
    vb = viewbox or f"0 0 {w} {h}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="{vb}" '
        f'font-family="-apple-system, Segoe UI, sans-serif">'
    )


# ── 1. Direction arrow (single passage event) ───────────────────────
def direction_arrow(direction: str | None,
                     anomaly_hint: str | None = None,
                     size: int = 64) -> str:
    """64×64 SVG: arrow + anomaly badge.

    direction: 'in' | 'out' | None
    anomaly_hint: 'forced' | 'held' | 'tailgating' | 'exit_without_entry' |
                   'denied_but_opened' | None
    """
    if anomaly_hint:
        color = _PALETTE["anomaly"]
    elif direction == "in":
        color = _PALETTE["in"]
    elif direction == "out":
        color = _PALETTE["out"]
    else:
        color = _PALETTE["neutral"]

    parts = [_svg_header(size, size)]
    # Background circle
    parts.append(
        f'<circle cx="{size/2}" cy="{size/2}" r="{size/2 - 2}" '
        f'fill="{_PALETTE["bg"]}" stroke="{color}" stroke-width="2"/>'
    )
    # Arrow shape: ➜ pointing right for 'in', left for 'out',
    # diagonal cross for unknown
    cx, cy = size / 2, size / 2
    if direction == "in":
        # Right-pointing arrow
        parts.append(
            f'<path d="M {cx-14} {cy} L {cx+10} {cy} M {cx+4} {cy-8} '
            f'L {cx+12} {cy} L {cx+4} {cy+8}" stroke="{color}" '
            f'stroke-width="3" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round"/>'
        )
    elif direction == "out":
        parts.append(
            f'<path d="M {cx+14} {cy} L {cx-10} {cy} M {cx-4} {cy-8} '
            f'L {cx-12} {cy} L {cx-4} {cy+8}" stroke="{color}" '
            f'stroke-width="3" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round"/>'
        )
    else:
        # X cross
        parts.append(
            f'<path d="M {cx-10} {cy-10} L {cx+10} {cy+10} M {cx+10} '
            f'{cy-10} L {cx-10} {cy+10}" stroke="{color}" '
            f'stroke-width="3" fill="none" stroke-linecap="round"/>'
        )
    # Anomaly badge in corner
    if anomaly_hint:
        glyph = _ANOMALY_GLYPHS.get(anomaly_hint, "!")
        parts.append(
            f'<circle cx="{size-12}" cy="12" r="10" fill="{color}" '
            f'stroke="white" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{size-12}" y="17" font-size="14" fill="white" '
            f'text-anchor="middle" font-weight="bold">{escape(glyph)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


# ── 2. Temporal heatmap 24h × 7d ─────────────────────────────────────
_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def heatmap_24h_7d(buckets, title: str = "",
                    max_count: int | None = None,
                    width: int = 720, cell_h: int = 32) -> str:
    """24h × 7d temporal heatmap.

    buckets: list of 168 ints — buckets[weekday*24 + hour] = count
             (weekday 0=Mon, 6=Sun)
    """
    if not buckets or len(buckets) != 168:
        buckets = [0] * 168
    max_v = max_count if max_count is not None else max(max(buckets, default=0), 1)

    margin_left = 50
    margin_top = 30
    margin_bottom = 18
    grid_w = width - margin_left - 8
    cell_w = grid_w / 24
    grid_h = 7 * cell_h
    height = margin_top + grid_h + margin_bottom

    parts = [_svg_header(width, height)]
    # Title
    if title:
        parts.append(
            f'<text x="{margin_left}" y="18" font-size="13" '
            f'fill="{_PALETTE["text"]}" font-weight="600">'
            f'{escape(title)}</text>'
        )

    # Hour labels (every 3h)
    for h in range(0, 25, 3):
        x = margin_left + h * cell_w
        parts.append(
            f'<text x="{x}" y="{margin_top - 4}" font-size="10" '
            f'fill="{_PALETTE["neutral"]}" text-anchor="middle">'
            f'{h:02d}</text>'
        )

    # Cells
    for day in range(7):
        # Day label
        parts.append(
            f'<text x="{margin_left - 8}" y="{margin_top + day * cell_h + cell_h*0.65}" '
            f'font-size="10" fill="{_PALETTE["neutral"]}" '
            f'text-anchor="end">{_WEEKDAY_LABELS[day]}</text>'
        )
        for hour in range(24):
            count = buckets[day * 24 + hour]
            intensity = count / max_v if max_v else 0
            color = _heatmap_color(intensity)
            x = margin_left + hour * cell_w
            y = margin_top + day * cell_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y}" width="{cell_w - 1:.1f}" '
                f'height="{cell_h - 1}" fill="{color}">'
                f'<title>{_WEEKDAY_LABELS[day]} {hour:02d}:00 — '
                f'{count} passage{"s" if count != 1 else ""}</title>'
                f'</rect>'
            )

    # Legend
    legend_x = margin_left
    legend_y = margin_top + grid_h + 10
    for i in range(6):
        intensity = i / 5
        color = _heatmap_color(intensity)
        parts.append(
            f'<rect x="{legend_x + i * 18}" y="{legend_y - 6}" '
            f'width="16" height="6" fill="{color}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 6 * 18 + 4}" y="{legend_y}" '
        f'font-size="10" fill="{_PALETTE["neutral"]}">0 → {max_v}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def _heatmap_color(intensity: float) -> str:
    """Blue gradient: 0 → light, 1 → dark."""
    intensity = max(0.0, min(1.0, intensity))
    if intensity == 0:
        return _PALETTE["bg"]
    # Lerp between #E3F2FD (light) and #0D47A1 (dark)
    r = int(0xE3 + (0x0D - 0xE3) * intensity)
    g = int(0xF2 + (0x47 - 0xF2) * intensity)
    b = int(0xFD + (0xA1 - 0xFD) * intensity)
    return f"#{r:02X}{g:02X}{b:02X}"


# ── 3. Site map with device placements + live state ──────────────────
def site_map_with_devices(facility_name: str,
                           placements: list[dict],
                           access_points: list[dict] | None = None,
                           width: int = 800, height: int = 600,
                           background_url: str | None = None) -> str:
    """Floorplan-style SVG с overlay-нати devices в нормализирани coords.

    placements: list of {'name', 'device_kind', 'nx', 'ny',
                          'bearing_degrees', 'fov_degrees',
                          'status_color', 'id'}
    access_points: list of {'name', 'nx', 'ny', 'live_state',
                             'point_type', 'id'}
                   live_state: 'idle' | 'in' | 'out' | 'anomaly'
    background_url: optional Odoo image URL для floor plan (overlay above)
    """
    placements = placements or []
    access_points = access_points or []

    parts = [_svg_header(width, height)]
    # Background
    if background_url:
        parts.append(
            f'<image href="{escape(background_url)}" x="0" y="0" '
            f'width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet" '
            f'opacity="0.85"/>'
        )
    else:
        parts.append(
            f'<rect x="0" y="0" width="{width}" height="{height}" '
            f'fill="{_PALETTE["bg"]}" stroke="{_PALETTE["grid"]}"/>'
        )
        # Grid hints
        for i in range(1, 10):
            x = width * i / 10
            parts.append(
                f'<line x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{height}" '
                f'stroke="{_PALETTE["grid"]}" stroke-width="0.5"/>'
            )
            y = height * i / 10
            parts.append(
                f'<line x1="0" y1="{y:.0f}" x2="{width}" y2="{y:.0f}" '
                f'stroke="{_PALETTE["grid"]}" stroke-width="0.5"/>'
            )

    # Title
    parts.append(
        f'<text x="{width/2}" y="22" font-size="14" '
        f'fill="{_PALETTE["text"]}" text-anchor="middle" '
        f'font-weight="600">{escape(facility_name)}</text>'
    )

    # Camera FOV cones (rendered под другите elements за visibility)
    for p in placements:
        if p.get("device_kind") == "camera" and p.get("fov_degrees"):
            cx = width * p["nx"]
            cy = height * p["ny"]
            bearing = p.get("bearing_degrees", 0)
            fov = p["fov_degrees"]
            rng = max(40, min(150, p.get("range_meters", 50) * 1.5))
            parts.append(_fov_cone(cx, cy, bearing, fov, rng))

    # Access points (doors / barriers) — rendered as larger badges
    for ap in access_points:
        cx = width * ap.get("nx", 0.5)
        cy = height * ap.get("ny", 0.5)
        state = ap.get("live_state", "idle")
        state_color = {
            "in": _PALETTE["in"],
            "out": _PALETTE["out"],
            "anomaly": _PALETTE["anomaly"],
            "idle": _PALETTE["neutral"],
        }.get(state, _PALETTE["neutral"])
        # Door icon (door-shaped rect)
        parts.append(
            f'<rect x="{cx-10}" y="{cy-14}" width="20" height="28" rx="3" '
            f'fill="white" stroke="{state_color}" stroke-width="2"/>'
        )
        parts.append(
            f'<circle cx="{cx+5}" cy="{cy}" r="1.5" fill="{state_color}"/>'
        )
        # State pulse если активно
        if state in ("in", "out", "anomaly"):
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="18" fill="none" '
                f'stroke="{state_color}" stroke-width="1.5" opacity="0.5">'
                f'<animate attributeName="r" from="14" to="22" '
                f'dur="1.5s" repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" from="0.6" to="0" '
                f'dur="1.5s" repeatCount="indefinite"/>'
                f'</circle>'
            )
        # Label
        parts.append(
            f'<text x="{cx}" y="{cy+26}" font-size="9" '
            f'fill="{_PALETTE["text"]}" text-anchor="middle">'
            f'{escape((ap.get("name") or "")[:20])}</text>'
        )

    # Device placements (readers/magnets/etc.)
    for p in placements:
        cx = width * p["nx"]
        cy = height * p["ny"]
        kind = p.get("device_kind", "other")
        color = (p.get("status_color") or
                 _PALETTE.get(kind, _PALETTE["neutral"]))
        parts.append(_device_icon(cx, cy, kind, color, p.get("name", "")))

    parts.append("</svg>")
    return "".join(parts)


def _fov_cone(cx: float, cy: float, bearing: float, fov: float,
               rng: float) -> str:
    """SVG path за камера FOV cone."""
    import math
    half = fov / 2
    # Bearing 0 = North (up); SVG y axis inverted
    b_rad = math.radians(bearing - 90)  # rotate so 0=up
    l_rad = b_rad - math.radians(half)
    r_rad = b_rad + math.radians(half)
    lx = cx + rng * math.cos(l_rad)
    ly = cy + rng * math.sin(l_rad)
    rx = cx + rng * math.cos(r_rad)
    ry = cy + rng * math.sin(r_rad)
    return (
        f'<path d="M {cx} {cy} L {lx:.1f} {ly:.1f} '
        f'A {rng:.0f} {rng:.0f} 0 0 1 {rx:.1f} {ry:.1f} Z" '
        f'fill="{_PALETTE["camera"]}" opacity="0.15" '
        f'stroke="{_PALETTE["camera"]}" stroke-width="0.5" '
        f'stroke-dasharray="2 2"/>'
    )


def _device_icon(cx: float, cy: float, kind: str, color: str,
                  label: str) -> str:
    """Малък icon на устройство."""
    if kind == "camera":
        # Camera body
        shape = (
            f'<rect x="{cx-7}" y="{cy-5}" width="14" height="10" rx="1.5" '
            f'fill="{color}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="3" fill="white"/>'
            f'<circle cx="{cx}" cy="{cy}" r="1.5" fill="{color}"/>'
        )
    elif kind in ("reader", "rfid_reader", "biometric"):
        shape = (
            f'<rect x="{cx-5}" y="{cy-6}" width="10" height="12" rx="2" '
            f'fill="{color}"/>'
            f'<line x1="{cx-3}" y1="{cy-3}" x2="{cx+3}" y2="{cy-3}" '
            f'stroke="white" stroke-width="1"/>'
            f'<line x1="{cx-3}" y1="{cy}" x2="{cx+3}" y2="{cy}" '
            f'stroke="white" stroke-width="1"/>'
            f'<line x1="{cx-3}" y1="{cy+3}" x2="{cx+3}" y2="{cy+3}" '
            f'stroke="white" stroke-width="1"/>'
        )
    elif kind in ("magnet", "lock", "magnetic_lock"):
        # Лилав диамант
        shape = (
            f'<path d="M {cx} {cy-6} L {cx+5} {cy} L {cx} {cy+6} '
            f'L {cx-5} {cy} Z" fill="{color}"/>'
        )
    else:
        shape = (
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>'
        )
    # Small label
    txt = ""
    if label:
        txt = (
            f'<text x="{cx}" y="{cy+16}" font-size="8" '
            f'fill="{_PALETTE["text"]}" text-anchor="middle">'
            f'{escape(label[:14])}</text>'
        )
    return shape + txt
