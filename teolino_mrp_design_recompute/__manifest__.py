{
    "name": "Teolino MRP Design Recompute",
    "version": "18.0.1.6.0",
    "summary": "Live BoM sim + per-shutter eval + PTAV color resolution (simulate AND MO swap) + auto-recompute + cutting list PDF",
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
    ],
    "installable": True,
    "application": False,
}
