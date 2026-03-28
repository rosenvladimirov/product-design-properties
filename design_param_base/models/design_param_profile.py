# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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
        "SVG Content",
        help="Raw SVG XML content with named path IDs for 3D profile rendering.",
    )
    profile_definition = fields.Json(
        "Profile Definition",
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
        "Camera Distance",
        default=4.0,
        help="Distance of the 3D camera from the model center.",
    )
