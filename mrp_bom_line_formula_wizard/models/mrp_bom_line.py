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
from odoo import _, fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    has_quantity_formula = fields.Boolean(
        compute="_compute_has_quantity_formula",
        store=False,
    )

    def _compute_has_quantity_formula(self):
        for line in self:
            line.has_quantity_formula = bool(line.quantity_formula)

    def action_edit_formula(self):
        """Open the formula editor wizard for this BoM line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Edit Quantity Formula"),
            "res_model": "mrp.bom.line.formula.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bom_line_id": self.id,
                "default_quantity_formula": self.quantity_formula or "",
                "default_product_name": self.product_id.display_name,
            },
        }
