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
    "name": "Sale Design Pricing — cost+ markup для design products",
    "version": "18.0.1.3.3",
    "summary": "Cost-plus pricing for parametric design products (separate material/labor markups)",
    "author": "Rosen Vladimirov",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "AGPL-3",
    "category": "Sales/Sales",
    "depends": [
        "sale",
        "mrp",
        "sale_design_configurator",
    ],
    "data": [
        "security/ir.model.access.csv",
        # Re-enabled 2026-06-08: markup полета (Settings / категория / продукт)
        # + „Калкулация (admin)" таб на SO реда. Бяха временно изключени заради
        # stale view records от стар failed install на Vladimir-овия build; на
        # dev-teo-2305 (чист клон) няма конфликтни view-ове (проверено).
        "views/res_config_settings_views.xml",
        "views/product_category_views.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
