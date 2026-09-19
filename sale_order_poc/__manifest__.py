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
    "name": "Sale Order Production Configuration",
    "summary": "Production configuration of a sale order line: parameters "
    "from templates, derived values, lot link",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    # 🔑 LGPL гръбнак (ADR sale-order-poc/0005): на него стъпват и OPL, и
    # AGPL модули, затова не зависи от нито един от тях.
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "base_formula_engine",
    ],
    "data": [
        "security/sale_order_poc_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/poc_param_views.xml",
        "views/poc_template_views.xml",
        "views/sale_order_poc_views.xml",
        "views/sale_order_views.xml",
        "views/product_template_views.xml",
        "views/stock_lot_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/poc_demo.xml",
    ],
    "installable": True,
    "application": False,
}
