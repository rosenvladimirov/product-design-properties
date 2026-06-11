# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Product Design Assets",
    "summary": (
        "Link design visual assets (GLB, SVG, PNG) "
        "from product attachments for 3D configurators"
    ),
    "version": "18.0.1.1.0",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["product", "mrp", "design_param_base"],
    "data": [
        "views/product_views.xml",
    ],
}
