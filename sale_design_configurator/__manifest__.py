# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
{
    "name": "Sale Design Configurator",
    "summary": (
        "SO line design configurator with 3D preview " "for parametric manufacturing"
    ),
    "version": "19.0.1.49.1",
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
        "purchase_stock",
        # JS bundle-ът импортва @mrp_design_matrix/... (t0_evaluate,
        # RuleMatrixPreview) → твърда зависимост; без нея чиста инсталация
        # чупи web.assets_backend.
        "mrp_design_matrix",
    ],
    "data": [
        "security/design_groups.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_lot_views.xml",
        "views/sale_order_views.xml",
        "views/product_views.xml",
        "views/design_sales_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # three.js се vendor-ва ЛОКАЛНО (беше публичен cdnjs CDN на всяка
            # backend страница: supply-chain/GDPR/offline риск). MIT headers
            # възстановени на трите файла (лицензно изискване).
            "sale_design_configurator/static/lib/three/three.min.js",
            "sale_design_configurator/static/lib/three/GLTFLoader.js",
            "sale_design_configurator/static/lib/three/meshopt_decoder.js",
            "sale_design_configurator/static/src/components/**/*",
        ],
    },
}
