# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Access Control (ZEN-driven)",
    "summary": (
        "Polymorphic physical access control: subjects, perimeters, "
        "control points, ZEN-driven decision flow with offline sync."
    ),
    "version": "19.0.1.0.0",
    "category": "Security",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "BL Consulting, Odoo Community Association (OCA)",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base",
        "hr",
        "resource",
        "mrp_design_matrix",            # transitional kernel host (ZEN)
        "hr_attendance_access_control", # legacy bridge (cards, controllers)
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/access_subject_views.xml",
        "views/access_credential_views.xml",
        "views/access_perimeter_views.xml",
        "views/access_control_point_views.xml",
        "views/access_passage_event_views.xml",
        "views/access_violation_views.xml",
        "views/access_occupancy_views.xml",
        "views/menu.xml",
        "data/zen_graph_access_default.xml",
    ],
    "demo": [],
}
