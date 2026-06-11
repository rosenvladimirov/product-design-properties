# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP BoM Line Formula Wizard",
    "summary": "Edit BoM line quantity formulas in a dedicated wizard with syntax help",
    "version": "18.0.2.0.0",
    "author": "Rosen Vladimirov, BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "category": "Manufacturing",
    "depends": [
        "mrp_bom_line_formula_template",
    ],
    "website": "https://github.com/OCA/manufacture",
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "wizard/formula_editor_wizard_views.xml",
        "views/mrp_bom_views.xml",
    ],
    "installable": True,
    "application": False,
}
