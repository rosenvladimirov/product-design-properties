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
from odoo import fields, models


class DesignParamProfile(models.Model):
    _name = "design.param.profile"
    _description = "Design Parameter SVG Profile"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    definition_id = fields.Many2one(
        "design.param.definition",
        required=True,
        ondelete="cascade",
    )
    svg_content = fields.Text(
        help="Raw SVG XML content with named path IDs for 3D profile rendering.",
    )
    profile_definition = fields.Json(
        help=(
            "JSON mapping SVG element IDs to design parameters. "
            "Controls conditional visibility, colors, and extrusion depth."
        ),
    )
    extrude_depth = fields.Float(
        "Default Extrude Depth",
        default=0.05,
        help="Default depth (scene units) for extruding SVG paths into 3D.",
    )
    camera_distance = fields.Float(
        default=4.0,
        help="Distance of the 3D camera from the model center.",
    )
