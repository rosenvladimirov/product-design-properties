# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP Design Matrix — Roller Shutters",
    "summary": (
        "Design parameter definitions and matrix templates "
        "for roller shutter manufacturers (Teolino)."
    ),
    "version": "18.0.1.3.0",
    "category": "Manufacturing",
    "website": "https://github.com/OCA/manufacture",
    "author": "BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "post_init_hook": "post_init_hook",
    "depends": ["mrp_design_matrix"],
    "data": [
        "data/install_design_params.xml",
        "data/matrix_templates.xml",
    ],
    "demo": [
        "demo/demo_bom_roller_door.xml",
    ],
}
