# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
"""Помощниците `d` на SVG шаблона на рисунката (SPEC sale-order-poc/drawing § 3.2).

Чисти функции: само числа, низове, кортежи и речници. Нямат достъп до env,
до записи или до базата — шаблонът (QWeb в базата) ги вижда като `d.<име>`.
Размерите в mm дават само пропорциите; рисунката нищо не смята за цена или
BoM (ADR sale-order-poc/0025, т. 8).
"""

import math
import re
import types

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# стените на кутията — по ъглите от `box`
FACES = {
    "bottom": ("A", "B", "C", "D"),
    "top": ("A1", "B1", "C1", "D1"),
    "front": ("A", "B", "B1", "A1"),
    "back": ("D", "C", "C1", "D1"),
    "left": ("A", "D", "D1", "A1"),
    "right": ("B", "C", "C1", "B1"),
    # видимата странична стена в изометрията е лявата
    "side": ("A", "D", "D1", "A1"),
}


def num(value, default=0.0):
    """Число от стойността; празното или нечисловото дава ``default``."""
    if isinstance(value, bool) or value is None or value == "":
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def iso(l, w, h=0.0):  # noqa: E741 — дължина, ширина, височина
    """Изометричната проекция на Пакит: точка (l, w, h) → (x, y) в SVG.

    Оста по дължина и по ширина са огледални; височината расте нагоре.
    """
    l, w, h = num(l), num(w), num(h)
    return (-(l - w), l * -0.46 + w * -0.42 - h)


def _xy(point):
    """2D точка; 3D точката минава през `iso`."""
    if len(point) == 3:
        return iso(*point)
    return (num(point[0]), num(point[1]))


def pts(points):
    """Точките като ``"x,y x,y"`` за ``points=`` на polygon/polyline."""
    return " ".join("%.1f,%.1f" % _xy(point) for point in points)


def box(l, w, h, z=0.0, dx=0.0, dy=0.0):  # noqa: E741
    """Осемте ъгъла на кутия (3D): долу A B C D, горе A1 B1 C1 D1."""
    l, w, h, z, dx, dy = num(l), num(w), num(h), num(z), num(dx), num(dy)
    return {
        "A": (dx, dy, z),
        "B": (l + dx, dy, z),
        "C": (l + dx, w + dy, z),
        "D": (dx, w + dy, z),
        "A1": (dx, dy, z + h),
        "B1": (l + dx, dy, z + h),
        "C1": (l + dx, w + dy, z + h),
        "D1": (dx, w + dy, z + h),
    }


def face(corners, name):
    """Стената на кутията като списък от четири 3D ъгъла."""
    return [corners[key] for key in FACES[name]]


def flap(a, b, direction, depth):
    """Клапан по ръба a–b, отворен по посоката ``direction`` на ``depth``."""
    depth = num(depth)

    def tip(point):
        return tuple(num(point[i]) + num(direction[i]) * depth for i in range(3))

    return [a, b, tip(b), tip(a)]


def rect(x, y, w, h):
    """Правоъгълник като четири 2D точки (по часовниковата стрелка)."""
    x, y, w, h = num(x), num(y), num(w), num(h)
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def line(a, b):
    """Отсечка като ``d=`` на path."""
    (x1, y1), (x2, y2) = _xy(a), _xy(b)
    return "M%.1f %.1f L%.1f %.1f" % (x1, y1, x2, y2)


def dim_line(a, b, text="", offset=0.0, tick=None):
    """Размерна линия от a до b, изместена с ``offset`` по нормалата.

    Връща речник: ``d`` (path с изводните линии и чертичките), ``x``/``y``
    (къде да стои текстът), ``text``, ``angle`` и готов ``transform``
    (завъртането на текста по линията).
    """
    (x1, y1), (x2, y2) = _xy(a), _xy(b)
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux
    offset = num(offset)
    tick = num(tick, length * 0.03) if tick is not None else length * 0.03
    ax, ay = x1 + nx * offset, y1 + ny * offset
    bx, by = x2 + nx * offset, y2 + ny * offset
    parts = []
    if offset:
        parts += [line((x1, y1), (ax, ay)), line((x2, y2), (bx, by))]
    parts.append(line((ax, ay), (bx, by)))
    # чертичките под 45° в краищата
    for px, py in ((ax, ay), (bx, by)):
        parts.append(line(
            (px - (ux + nx) * tick / 2, py - (uy + ny) * tick / 2),
            (px + (ux + nx) * tick / 2, py + (uy + ny) * tick / 2),
        ))
    gap = tick * 1.2 if offset >= 0 else -tick * 1.2
    tx = (ax + bx) / 2 + nx * gap
    ty = (ay + by) / 2 + ny * gap
    angle = math.degrees(math.atan2(uy, ux))
    # текстът не стои с главата надолу
    # (вертикалният се чете отдолу нагоре)
    if angle >= 90:
        angle -= 180
    elif angle < -90:
        angle += 180
    return {
        "d": " ".join(parts),
        "x": round(tx, 1),
        "y": round(ty, 1),
        "text": text,
        "angle": round(angle, 1),
        "transform": "rotate(%.1f %.1f %.1f)" % (angle, tx, ty),
    }


def viewbox(points, pad=0.12):
    """``viewBox`` около точките, с поле ``pad`` (дял от по-голямата страна)."""
    xy = [_xy(point) for point in points] or [(0.0, 0.0)]
    xs = [x for x, _y in xy]
    ys = [y for _x, y in xy]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y) or 1.0
    margin = span * num(pad, 0.12)
    return "%.1f %.1f %.1f %.1f" % (
        min_x - margin,
        min_y - margin,
        max_x - min_x + 2 * margin,
        max_y - min_y + 2 * margin,
    )


def stroke_width(view_box, k=140.0):
    """Дебелината на линията по ``viewBox``: по-голямата страна / ``k``."""
    try:
        _x, _y, width, height = (float(part) for part in str(view_box).split())
    except ValueError:
        return "1"
    return "%.2f" % (max(width, height) / (num(k, 140.0) or 140.0))


def shade(color, k=0.85):
    """Цветът, потъмнен (``k`` < 1) или изсветлен (``k`` > 1)."""
    if not isinstance(color, str) or not HEX_RE.match(color):
        return color
    k = num(k, 1.0)
    channels = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    if k <= 1:
        channels = [round(c * k) for c in channels]
    else:
        channels = [round(c + (255 - c) * min(k - 1, 1)) for c in channels]
    return "#%02x%02x%02x" % tuple(max(0, min(255, c)) for c in channels)


def image_on_face(href, face_pts, size=None, src_rect=None):
    """Картинка върху стена — афинно, точно (SPEC § 3.8).

    ``face_pts`` — горе-ляво, горе-дясно и долу-ляво на стената, гледана
    отвън (3D или 2D точки). ``size`` — (ширина, височина) на стената в mm:
    картината пази пропорциите си вътре в нея; без него се разтяга.
    ``src_rect`` — (x, y, ширина, височина) от по-голяма картина (цялата
    разгъвка, ``size`` е тогава размерът ѝ): показва се само тази част.

    Връща речник за шаблона — ``transform``, ``href``, ``x``, ``y``,
    ``width``, ``height``, ``aspect`` и ``clip`` (правоъгълник или None) —
    или None без адрес. Шаблонът сам пише ``<g><image/></g>``, за да ескейпва
    QWeb атрибутите.
    """
    if not href or not isinstance(href, str):
        return None
    (ex, ey), (rx, ry), (bx, by) = (_xy(point) for point in face_pts[:3])
    if src_rect:
        sx, sy, w, h = (num(part) for part in src_rect)
        full_w, full_h = (num(part) for part in (size or (w, h)))
        x, y, width, height, clip = -sx, -sy, full_w, full_h, (0.0, 0.0, w, h)
        aspect = "none"
    elif size:
        w, h = num(size[0]), num(size[1])
        x, y, width, height, clip = 0.0, 0.0, w, h, None
        aspect = "xMidYMid meet"
    else:
        w = h = 1.0
        x, y, width, height, clip = 0.0, 0.0, 1.0, 1.0, None
        aspect = "none"
    w, h = w or 1.0, h or 1.0
    return {
        "transform": "matrix(%.5f %.5f %.5f %.5f %.3f %.3f)" % (
            (rx - ex) / w, (ry - ey) / w, (bx - ex) / h, (by - ey) / h, ex, ey),
        "href": href,
        "x": "%.1f" % x,
        "y": "%.1f" % y,
        "width": "%.1f" % width,
        "height": "%.1f" % height,
        "aspect": aspect,
        "clip": clip and "M%.1f %.1fH%.1fV%.1fH%.1fZ" % (
            clip[0], clip[1], clip[2], clip[3], clip[0]),
    }


def make_helpers(values):
    """Помощниците `d` за едно рендиране.

    ``color`` е затворен върху ``values`` (само прости стойности): приема
    готов ``#rrggbb`` или код на параметър — тогава чете ``<код>__color``.
    """

    def color(value, default="#ffffff"):
        if isinstance(value, str) and HEX_RE.match(value):
            return value
        if isinstance(value, str):
            linked = values.get("%s__color" % value)
            if isinstance(linked, str) and HEX_RE.match(linked):
                return linked
        return default

    return types.SimpleNamespace(
        num=num,
        iso=iso,
        pts=pts,
        box=box,
        face=face,
        flap=flap,
        rect=rect,
        line=line,
        dim_line=dim_line,
        viewbox=viewbox,
        stroke_width=stroke_width,
        shade=shade,
        color=color,
        image_on_face=image_on_face,
    )
