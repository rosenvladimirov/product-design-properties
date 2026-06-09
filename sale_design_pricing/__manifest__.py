{
    "name": "Sale Design Pricing — cost+ markup для design products",
    "version": "18.0.1.2.5",
    "summary": "Cost-plus pricing for parametric design products (separate material/labor markups)",
    "author": "Teolino",
    "license": "AGPL-3",
    "category": "Sales/Sales",
    "depends": [
        "sale",
        "mrp",
        "sale_design_configurator",
    ],
    "data": [
        "security/ir.model.access.csv",
        # Views temporarily disabled — Vladimir's Odoo build has stale view
        # records from earlier failed install attempts that conflict at view
        # validation time. Once those are cleaned via SQL (or fresh DB), put
        # them back:
        # "views/res_config_settings_views.xml",
        # "views/product_category_views.xml",
        # "views/product_template_views.xml",
        # "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
