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
    "name": "Sale Order Production Configuration Drawing",
    "summary": "Product drawing of a production configuration, managed as data "
    "of the template: picture, SVG template, defaults and caption",
    "version": "19.0.1.1.0",
    "category": "Sales/Sales",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    # ⚖️ LGPL: стъпва само на гръбнака sale_order_poc; НЕ зависи от AGPL
    # модули (product_design_assets, packit_*, mrp_design_matrix_*) —
    # ADR sale-order-poc/0025.
    "license": "LGPL-3",
    "depends": ["sale_order_poc"],
    "data": [
        "security/sale_order_poc_drawing_security.xml",
        "security/ir.model.access.csv",
        "data/sale_order_poc_drawing_data.xml",
        "views/sale_order_poc_drawing_views.xml",
        "views/poc_template_views.xml",
        "views/sale_order_poc_views.xml",
        "views/poc_param_views.xml",
        "views/product_views.xml",
        "views/report_templates.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
