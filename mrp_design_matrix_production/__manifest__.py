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
    "name": "MRP Design Matrix — MO Configuration & Lifecycle",
    "summary": (
        "Anchor the design-matrix configuration on the manufacturing order "
        "instead of the lot: it travels through backorders, splits, merges "
        "and down into semi-finished child MOs, controls the produced lot and "
        "stamps a data fingerprint into the lot description."
    ),
    "version": "1.0.0",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    # Design-matrix engine — provides design.param.definition._build_context,
    # mrp.production._resolve_design_context, stock.lot design config.
    "depends": [
        "mrp_design_matrix",
    ],
    "data": [
        "views/mrp_production_views.xml",
    ],
}
