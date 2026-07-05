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
from odoo import _, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_open_design_production(self):
        """Open the full design of the producing lot for review/correction.

        Production level: the generic configurator is opened in ``production``
        mode — ALL parameter levels visible (review), editable for correction.
        Driven by param_levels; no client-specific logic.
        """
        self.ensure_one()
        lot = self.lot_producing_ids[:1]
        definition = (
            lot.design_param_definition_id
            or (self.bom_id and self.bom_id.design_param_definition_id)
        )
        if not definition:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design parameter set"),
                    "message": _("This MO has no design parameter definition."),
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": definition.id,
                "existingLotId": lot.id if lot else False,
                "moId": self.id,
                "level": "production",
            },
        }
