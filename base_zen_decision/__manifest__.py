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
    "name": "Base ZEN Decision",
    "summary": (
        "ZEN/GoRules decision-table kernel: evaluate + trace + version + "
        "sync. Domain-agnostic host for mrp_design_matrix, access_control."
    ),
    "version": "19.0.1.2.0",
    "category": "Technical",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
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
