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
    "name": "Technical Check Design Configurator",
    "summary": (
        "Technical-level design stage: own tablet menu + queue, fills "
        "technical-level parameters on the design lot. Generic, "
        "parameter-driven (reads param_levels)."
    ),
    "version": "19.0.1.4.1",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "sale_design_configurator",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/technical_design_views.xml",
        "wizards/design_lot_create_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "technical_check_design_configurator/static/src/scss/tablet.scss",
        ],
    },
}
