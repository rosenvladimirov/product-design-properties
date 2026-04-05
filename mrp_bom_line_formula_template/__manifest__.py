# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP BoM Line Formula Templates",
    "summary": "Manage reusable templates for BoM line quantity formulas",
    "version": "18.0.1.2.1",
    "author": "Rosen Vladimirov, BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "category": "Manufacturing",
    "depends": [
        "mrp",
        "mrp_bom_line_formula_quantity",
    ],
    "website": "https://github.com/OCA/manufacture",
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "security/formula_template_rules.xml",
        "views/mrp_bom_line_formula_template_views.xml",
    ],
    "installable": True,
    "application": False,
}
