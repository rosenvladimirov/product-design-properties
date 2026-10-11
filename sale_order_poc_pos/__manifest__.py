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
    "name": "Sale Order Production Configuration in the Point of Sale",
    "summary": "Touch editor of the production configuration of a wholesale "
    "line in the Point of Sale",
    "version": "19.0.1.1.0",
    "category": "Sales/Point of Sale",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "LGPL-3",
    # Лепило: продажбата на едро в касата като оферта (l10n_bg_pos_b2b_sale)
    # + конфигурацията на реда (sale_order_poc). ADR pos-b2b-wholesale/0004.
    "depends": ["l10n_bg_pos_b2b_sale", "sale_order_poc"],
    "auto_install": True,
    "assets": {
        "point_of_sale._assets_pos": [
            "sale_order_poc_pos/static/src/app/**/*",
        ],
        "web.assets_tests": [
            "sale_order_poc_pos/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
