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
    "name": "MRP Design Matrix — Cost & Price",
    "summary": (
        "Parametric design cost roll-up (materials + labour) over the design "
        "matrix, Teolino-style markup for a suggested sale price, and a "
        "read-only field link that pulls the real sale price from the standard "
        "pricelist/product (the matrix only reads the price, never writes it)."
    ),
    "version": "19.0.1.7.3",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "mrp_design_matrix",
        "sale_design_configurator",
    ],
    "data": [
        "security/design_groups.xml",
        "data/sentinel_cron.xml",
        "views/product_template_views.xml",
        "views/mrp_bom_views.xml",
        "views/stock_lot_views.xml",
        "report/report_cut_list.xml",
    ],
}
