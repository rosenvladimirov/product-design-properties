# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""HTML dashboard landing pages — embed-ват SVG-тата във full-page view."""

from xml.sax.saxutils import escape

from odoo import http
from odoo.http import request


_PAGE_TPL = """<!doctype html>
<html lang="bg"><head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body {{
    margin: 0; font-family: -apple-system, Segoe UI, sans-serif;
    background: #FAFBFC; color: #2C3E50;
  }}
  .top {{
    background: #2C3E50; color: white; padding: 12px 20px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .top h1 {{ margin: 0; font-size: 18px; font-weight: 600; }}
  .top a {{ color: #95A5A6; text-decoration: none; font-size: 13px; }}
  .top a:hover {{ color: white; }}
  .grid {{
    display: grid; grid-template-columns: 1fr; gap: 16px;
    padding: 16px; max-width: 1200px; margin: 0 auto;
  }}
  .card {{
    background: white; border-radius: 6px; padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .card h2 {{
    margin: 0 0 12px 0; font-size: 14px; color: #7F8C8D;
    text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;
  }}
  .card img, .card svg {{ width: 100%; height: auto; display: block; }}
  .meta {{
    display: flex; gap: 16px; margin-top: 8px;
    font-size: 12px; color: #7F8C8D;
  }}
  .meta b {{ color: #2C3E50; }}
  @media (min-width: 900px) {{
    .grid {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head><body>
<div class="top">
  <h1>{title}</h1>
  <a href="/web">↩ Back to Odoo</a>
</div>
<div class="grid">{body}</div>
</body></html>
"""


class AccessControlDashboard(http.Controller):

    @http.route("/access_control/dashboard", type="http", auth="user",
                methods=["GET"], csrf=False)
    def dashboard_home(self, **kw):
        """Top dashboard — facility map + heatmaps на perimeters."""
        Facility = request.env["access.facility"].sudo()
        Perimeter = request.env["access.perimeter"].sudo()
        Occ = request.env["access.occupancy"].sudo()

        cards = []
        # Site map per facility (top)
        for f in Facility.search([("active", "=", True)]):
            cards.append(
                f'<div class="card"><h2>Site Map — {escape(f.name)}</h2>'
                f'<img src="/access_control/svg/site/{f.id}" alt="map"/>'
                f'<div class="meta">'
                f'<span>Address: <b>{escape(f.notes or "—")}</b></span>'
                f'</div></div>'
            )
        # Heatmap per perimeter
        for p in Perimeter.search([("active", "=", True)]):
            inside = Occ.search_count([
                ("perimeter_id", "=", p.id),
                ("state", "=", "inside"),
            ])
            cards.append(
                f'<div class="card"><h2>Heatmap — {escape(p.name or p.code)}</h2>'
                f'<img src="/access_control/svg/heatmap/{p.id}?days=30" alt="heatmap"/>'
                f'<div class="meta">'
                f'<span>Code: <b>{escape(p.code or "")}</b></span>'
                f'<span>Currently inside: <b>{inside}</b></span>'
                f'<span>Tolerance: <b>{p.tolerance_minutes} min</b></span>'
                f'</div></div>'
            )

        if not cards:
            cards.append(
                '<div class="card"><h2>No data yet</h2>'
                '<p>Create perimeters or wait for activity.</p></div>'
            )
        body = "\n".join(cards)
        html = _PAGE_TPL.format(title="Access Control · Dashboard", body=body)
        return request.make_response(
            html, headers=[("Content-Type", "text/html; charset=utf-8")])
