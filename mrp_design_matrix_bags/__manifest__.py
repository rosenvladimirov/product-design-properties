# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "MRP Design Matrix — Bags",
    "summary": (
        "Design parameter definitions and matrix templates "
        "for garbage bag manufacturers."
    ),
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
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
        "demo/demo_bom_bags.xml",
    ],
}
