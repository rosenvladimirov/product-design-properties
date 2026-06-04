# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP Design Matrix — Roller Shutters (5 models)",
    "summary": (
        "Full parametric design matrix for a 5-model roller-shutter "
        "range: Standard, Round, T-Roll, Built-In and Thermo Comfort."
    ),
    "version": "18.0.1.6.1",
    "category": "Manufacturing",
    "website": "https://github.com/OCA/manufacture",
    "author": "BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["mrp_design_matrix"],
    "data": [
        "data/install_design_params.xml",
        "data/workcenters.xml",
        "data/matrix_template_db_export.xml",
    ],
    "demo": [
        "demo/demo_bom_shutter_standard.xml",
    ],
}
