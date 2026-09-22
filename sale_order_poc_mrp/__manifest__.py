# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
{
    "name": "Sale Order Production Configuration - Manufacturing",
    "summary": "Production configuration of the sale order line on the "
    "manufacturing order: lot, no merging, recompute from configuration",
    "version": "19.0.1.2.0",
    "category": "Manufacturing/Manufacturing",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    # 🔑 LGPL мост (ADR sale-order-poc/0005): без формулен двигател — Stage 2
    # идва от AGPL листа sale_order_poc_mrp_formula, ако е инсталиран
    "license": "LGPL-3",
    "depends": [
        "sale_order_poc",
        "sale_mrp",
    ],
    "data": [
        "security/sale_order_poc_mrp_security.xml",
        "views/mrp_production_views.xml",
        "views/mrp_workorder_views.xml",
        "views/mrp_bom_views.xml",
        "views/sale_order_poc_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "sale_order_poc_mrp/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
