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
from . import models


def pre_init_hook(env):
    """Отказва инсталация върху стар PDP или върху стария форк.

    ``add_products`` и разгръщането му в MO дойдоха с 19.0.2.3.0 (ADR
    sale-order-poc/0012); без тях таблиците на конфигурацията нямат път до
    производството. ``mrp_bom_line_formula_quantity`` е изоставеният форк
    на същия двигател.
    """
    from odoo.exceptions import UserError
    from odoo.modules.module import get_manifest

    fork = env["ir.module.module"].search(
        [
            ("name", "=", "mrp_bom_line_formula_quantity"),
            ("state", "=", "installed"),
        ],
        limit=1,
    )
    if fork:
        raise UserError(
            env._(
                "Uninstall mrp_bom_line_formula_quantity first: it is the old "
                "fork of the same formula engine."
            )
        )
    version = get_manifest("mrp_bom_line_formula_template").get("version", "")
    parts = tuple(int(part) for part in version.split(".") if part.isdigit())
    if parts < (19, 0, 2, 3, 0):
        raise UserError(
            env._(
                "mrp_bom_line_formula_template %(version)s is too old; "
                "19.0.2.3.0 or later is needed for add_products.",
                version=version or "?",
            )
        )
