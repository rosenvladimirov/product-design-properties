# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Design Parameter Base",
    "summary": (
        "Shared design parameter definitions "
        "with SVG profiles for parametric manufacturing"
    ),
    "version": "18.0.1.1.1",
    "category": "Manufacturing",
    "website": "https://github.com/OCA/manufacture",
    "author": "Rosen Vladimirov, BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["stock", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "security/design_param_rules.xml",
        "data/design_industry_data.xml",
        "data/install_design_params.xml",
        "views/design_industry_views.xml",
        "views/design_param_definition_views.xml",
        "views/design_param_profile_views.xml",
        "views/mrp_bom_views.xml",
    ],
}
