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
    "name": "Base ZEN Decision — MRP menu glue",
    "summary": (
        "Glue: surfaces the ZEN Decisions menu under Manufacturing / "
        "Configuration. Keeps the base_zen_decision kernel domain-agnostic "
        "(no mrp dependency) while giving MRP users UI access to the "
        "decision tables and audit log."
    ),
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    # Автоматично се инсталира, когато и base_zen_decision, и mrp са налични —
    # така менюто се появява без ръчна намеса, а kernel-ът остава base-only.
    "auto_install": True,
    "depends": [
        "base_zen_decision",
        "mrp",
    ],
    "data": [
        "views/zen_menu_mrp_views.xml",
    ],
}
