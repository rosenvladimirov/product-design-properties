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
"""Bridge между access.control.point (new) и site_map's access.access_point
(съществуващ модел в hr_attendance_access_control_site_map).

Connection чрез optional m2o — control point може да бъде "the same as"
access_point (e.g. front door с reader + magnet + door). Това позволява
site map визуализациите да показват live state на новия decision flow.
"""

from odoo import api, fields, models


class AccessControlPointSite(models.Model):
    _inherit = "access.control.point"

    site_access_point_id = fields.Many2one(
        "access.access_point", string="Site Map Point",
        ondelete="set null",
        help="Linked physical point in the site map layer "
             "(facility/building/floor/area + position). Used от SVG "
             "live state overlays и за device_placement linkage.")

    @api.onchange("site_access_point_id")
    def _onchange_site_access_point(self):
        if self.site_access_point_id and not self.controller_id:
            self.controller_id = self.site_access_point_id.controller_id


class AccessFacilitySvg(models.Model):
    _inherit = "access.facility"

    def action_view_site_svg(self):
        """Open SVG site map в new tab (или embedded action)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/access_control/svg/site/{self.id}",
            "target": "new",
        }
