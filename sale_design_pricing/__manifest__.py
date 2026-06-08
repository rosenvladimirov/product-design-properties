{
    "name": "Sale Design Pricing — cost+ markup для design products",
    "version": "18.0.1.3.2",
    "summary": "Cost-plus pricing for parametric design products (separate material/labor markups)",
    "author": "Rosen Vladimirov",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "LGPL-3",
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
