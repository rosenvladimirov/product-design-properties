{
    "name": "Teolino Sale Design Configurator UI",
    "version": "18.0.1.9.1",
    "summary": "Per-model filtering, constraints, LIVE BoM preview, and per-component color sub-modal for the shutter design configurator",
    "author": "Teolino",
    "license": "AGPL-3",
    "category": "Sales/Sales",
    "depends": [
        "sale_design_configurator",
        "teolino_mrp_design_recompute",
    ],
    "assets": {
        "web.assets_backend": [
            "teolino_sale_design_configurator_ui/static/src/components/teolino_constraints.js",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_color_dialog/teolino_color_dialog.scss",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_color_dialog/teolino_color_dialog.js",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_color_dialog/teolino_color_dialog.xml",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_dialog/teolino_dialog.scss",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_dialog/teolino_dialog.js",
            "teolino_sale_design_configurator_ui/static/src/components/teolino_dialog/teolino_dialog.xml",
        ],
    },
    "installable": True,
    "application": False,
}
