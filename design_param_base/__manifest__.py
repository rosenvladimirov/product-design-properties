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
    "name": "Design Parameter Base",
    "summary": (
        "Shared design parameter definitions "
        "with SVG profiles for parametric manufacturing"
    ),
    "version": "20.0.1.1.1",
    "category": "Manufacturing",
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["stock", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "security/design_param_rules.xml",
        "data/design_industry_data.xml",
        "data/install_design_params.xml",
        "views/design_industry_views.xml",
        "views/design_param_definition_views.xml",
        "views/design_param_profile_views.xml",
        "views/mrp_bom_views.xml",
    ],
}
