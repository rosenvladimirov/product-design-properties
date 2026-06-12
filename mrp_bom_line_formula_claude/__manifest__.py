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
    "name": "MRP BoM Line Formula Claude Assistant",
    "summary": "Generate BoM line quantity formulas with Claude AI via MCP terminal",
    "version": "1.0.0",
    "author": "Rosen Vladimirov",
    "maintainers": ["rosen-vladimirov"],
    "category": "Manufacturing",
    "depends": [
        "mrp_bom_line_formula_wizard",
        "mrp_bom_line_formula_template",
        "l10n_bg_claude_terminal",
    ],
    "website": "https://github.com/rosenvladimirov/product-design-properties",
    "license": "AGPL-3",
    "data": [
        "wizard/formula_editor_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mrp_bom_line_formula_claude/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
