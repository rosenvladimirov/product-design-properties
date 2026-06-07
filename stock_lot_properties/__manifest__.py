# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Stock Lot Properties",
    "summary": (
        "Adds dynamic design parameters (Properties) "
        "to stock.lot linked to a definition model"
    ),
    "version": "20.0.1.0.0",
    "category": "Inventory",
    "website": "https://github.com/OCA/manufacture",
    "author": "Rosen Vladimirov, BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["stock", "design_param_base"],
    "data": [
        "views/stock_lot_views.xml",
    ],
}
