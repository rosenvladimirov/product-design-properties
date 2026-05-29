# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Access Control (ZEN-driven)",
    "summary": (
        "Polymorphic physical access control: subjects, perimeters, "
        "control points, ZEN-driven decision flow with offline sync."
    ),
    "version": "19.0.1.10.3",
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
        "hr_attendance_access_control_site_map",  # site/floor/devices
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
        "views/access_attendance_log_views.xml",
        "views/access_time_slot_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_department_views.xml",
        "views/hr_rfid_card_views.xml",
        "views/access_facility_svg_views.xml",
        "views/access_facility_dashboard_views.xml",
        "views/menu.xml",
        "wizards/access_controller_calibration_views.xml",
        "data/zen_graph_access_default.xml",
        "data/access_time_slot_data.xml",
    ],
    "demo": [],
}
