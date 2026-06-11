# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Design Configurator",
    "summary": (
        "SO line design configurator with 3D preview " "for parametric manufacturing"
    ),
    "version": "20.0.1.2.1",
    "category": "Sales",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "design_param_base",
        "stock_lot_properties",
        "product_design_assets",
        "sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_lot_views.xml",
        "views/sale_order_views.xml",
        "views/product_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js",
            "sale_design_configurator/static/lib/three/GLTFLoader.js",
            "sale_design_configurator/static/src/components/**/*",
        ],
    },
}
