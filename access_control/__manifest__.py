# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
{
    "name": "Access Control (ZEN-driven)",
    "summary": (
        "Polymorphic physical access control: subjects, perimeters, "
        "control points, ZEN-driven decision flow with offline sync."
    ),
    "version": "18.0.1.12.2",
    "category": "Security",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base",
        "hr",
        "resource",
        "base_zen_decision",            # ZEN decision-table kernel
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
        "views/access_controller_time_schedule_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_department_views.xml",
        "views/hr_rfid_card_views.xml",
        "views/access_facility_svg_views.xml",
        # menu.xml ПРЕДИ dashboard_views: последният ползва
        # %(action_access_dashboard_url)d, което menu.xml дефинира.
        "views/menu.xml",
        "views/access_facility_dashboard_views.xml",
        "wizards/access_controller_calibration_views.xml",
        "data/zen_graph_access_default.xml",
        "data/access_time_slot_data.xml",
    ],
    "demo": [],
}
