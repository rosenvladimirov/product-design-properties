{
    "name": "Teolino MRP Design Recompute",
    "version": "18.0.1.7.0",
    "summary": "Live BoM sim + per-shutter eval + PTAV color resolution + auto-recompute + cutting list PDF + active-only MO filter",
    "author": "Teolino",
    "license": "AGPL-3",
    "category": "Manufacturing",
    "depends": [
        "mrp",
        "mrp_bom_line_formula_template",
        "sale_design_pricing",
    ],
    "data": [
        "reports/mrp_production_cut_list.xml",
        "views/mrp_production_views.xml",
    ],
    "installable": True,
    "application": False,
}
