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
    "name": "MRP Operation Formula Templates",
    "summary": "Formula-driven work order duration, skip and material assignment per BoM operation",
    "version": "1.0.0",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "category": "Manufacturing",
    "depends": [
        "mrp_bom_line_formula_template",
    ],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "AGPL-3",
    "data": [
        "views/mrp_routing_workcenter_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
