# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP Design Matrix — Smart Home Display",
    "summary": (
        "Design parameter definitions and matrix templates "
        "for smart home display panel manufacturers."
    ),
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "website": "https://github.com/OCA/manufacture",
    "author": "Rosen Vladimirov, BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["mrp_design_matrix"],
    "data": [
        "data/install_design_params.xml",
        "data/matrix_templates.xml",
    ],
    "demo": [
        "demo/demo_bom_smart_display.xml",
    ],
}
