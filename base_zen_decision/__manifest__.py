# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Base ZEN Decision",
    "summary": (
        "ZEN/GoRules decision-table kernel: evaluate + trace + version + "
        "sync. Domain-agnostic host for mrp_design_matrix, access_control."
    ),
    "version": "20.0.1.0.0",
    "category": "Technical",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base",
    ],
    "external_dependencies": {
        "python": ["zen"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/zen_decision_views.xml",
    ],
    # Adopt the zen.* models/views/ACL previously owned by
    # mrp_design_matrix (Decision #4 Step 2 — kernel extraction). The
    # pre_init_hook reassigns their ir_model_data so the move does not
    # drop the existing tables/records.
    "pre_init_hook": "pre_init_hook",
}
