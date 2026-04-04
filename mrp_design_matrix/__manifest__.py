# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP Design Matrix",
    "summary": (
        "Parametric BoM driven by lot-level design parameters "
        "and a DMN rule matrix. Universal for make-to-order industries."
    ),
    "version": "18.0.1.3.0",
    "category": "Manufacturing",
    "website": "https://github.com/OCA/manufacture",
    "author": "BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "mrp",
        "stock",
        "purchase_stock",
        "design_param_base",
        "stock_lot_properties",
        "mrp_bom_line_formula_quantity",
        "stock_move_forced_lot_multi",
    ],
    "external_dependencies": {
        "python": ["zen"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/mrp_matrix_template_views.xml",
        "views/mrp_bom_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mrp_design_matrix/static/src/components/**/*",
        ],
    },
    "demo": [],
}
