#  Copyright 2026 Rosen Vladimirov - BL Consulting
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class MRPProduction(models.Model):
    _inherit = "mrp.production"

    def _get_move_raw_values(
        self,
        product,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        """Handle extended formula results (dict with product/uom overrides).

        The parent OCA module calls ``_eval_quantity_formula()`` and assigns
        the result directly to ``product_uom_qty``.  When our extended
        formula returns a dict ``{quantity, product, uom}``, this override
        unpacks it and applies product/uom overrides to the move values.
        """
        values = super()._get_move_raw_values(
            product,
            product_uom_qty,
            product_uom,
            operation_id=operation_id,
            bom_line=bom_line,
        )
        # The OCA super may have set product_uom_qty to a dict if our
        # extended _eval_quantity_formula returned one.
        qty_val = values.get("product_uom_qty")
        if isinstance(qty_val, dict):
            formula_result = qty_val
            values["product_uom_qty"] = formula_result.get("quantity", 0)
            if formula_result.get("product"):
                p = formula_result["product"]
                values["product_id"] = p.id
                values["name"] = p.display_name
            if formula_result.get("uom"):
                values["product_uom"] = formula_result["uom"].id
        return values
