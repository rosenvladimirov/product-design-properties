# Copyright 2026 Rosen Vladimirov
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
    "name": "Base Formula Engine",
    "summary": "Domain-agnostic formula templates and safe evaluation kernel",
    "version": "1.0.0",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "category": "Hidden/Tools",
    "depends": [
        "base",
    ],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "security/formula_template_rules.xml",
        "views/formula_template_views.xml",
    ],
    "installable": True,
    "application": False,
}
