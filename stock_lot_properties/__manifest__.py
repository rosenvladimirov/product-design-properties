# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Stock Lot Properties",
    "summary": (
        "Adds dynamic design parameters (Properties) "
        "to stock.lot linked to a definition model"
    ),
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["stock", "design_param_base"],
    "data": [
        "views/stock_lot_views.xml",
    ],
}
