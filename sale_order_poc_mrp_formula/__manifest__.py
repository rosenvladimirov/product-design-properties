# Copyright 2026 Rosen Vladimirov
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
    "name": "Sale Order Production Configuration - Formulas",
    "summary": "The configuration of the sale order line feeds the BoM line "
    "quantity formulas of the manufacturing order",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    # 🔑 AGPL лист (ADR sale-order-poc/0005): стъпва на AGPL формулите на PDP,
    # затова НИКОЙ LGPL или OPL модул не зависи от него. Инсталира се сам,
    # когато и двете страни ги има.
    "license": "AGPL-3",
    "depends": [
        "sale_order_poc_mrp",
        "mrp_bom_line_formula_template",
    ],
    "data": [
        "views/mrp_bom_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
