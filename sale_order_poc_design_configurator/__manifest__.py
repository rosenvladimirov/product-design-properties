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
    "name": "Sale Order Production Configuration - Design Configurator",
    "summary": "One order, one lot: the design configurator of the sale order "
    "line shows the configuration and prices the quotation from the matrix",
    "version": "19.0.1.1.0",
    "category": "Manufacturing/Manufacturing",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    # 🔑 AGPL лист (ADR sale-order-poc/0005): никой LGPL или OPL модул не
    # зависи от него. Частта без конфигуратора е в
    # sale_order_poc_design_matrix (ADR sale-order-poc/0019).
    "license": "AGPL-3",
    "depends": [
        "sale_order_poc_design_matrix",
        "sale_design_configurator",
        # цената на офертата: сухият пробег на матрицата и групата, която
        # вижда себестойността; двигателят на рецептата
        "mrp_design_matrix_cost",
        "mrp_account",
    ],
    "data": [
        "views/sale_order_poc_views.xml",
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "sale_order_poc_design_configurator/static/tests/tours/**/*",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
