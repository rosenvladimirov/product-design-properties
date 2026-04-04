#  Copyright 2024 Simone Rubino - Aion Tech
#  Copyright 2026 Rosen Vladimirov - BL Consulting
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class MRPBomLine(models.Model):
    _inherit = "mrp.bom.line"

    formula_template_id = fields.Many2one(
        "mrp.bom.line.formula.template",
        string="Quantity Formula Template",
    )
    quantity_formula = fields.Text(
        compute="_compute_quantity_formula",
        store=True,
        readonly=True,
    )

    @api.depends("formula_template_id", "formula_template_id.quantity_formula")
    def _compute_quantity_formula(self):
        for line in self:
            line.quantity_formula = line.formula_template_id.quantity_formula or False

    # ── Extended formula evaluation ──────────────────────────────────────

    def _quantity_formula_values(
        self,
        product,
        product_uom,
        product_uom_qty,
        production,
        operation_id=False,
        design_context=None,
    ):
        """Extend formula context with env and optional design context."""
        values = super()._quantity_formula_values(
            product,
            product_uom,
            product_uom_qty,
            production,
            operation_id=operation_id,
        )
        # Allow formulas to use env.ref(), env['model'].search(), etc.
        values["env"] = self.env
        # Inject design matrix context (width, height, T1 outputs, etc.)
        if design_context:
            values["design_context"] = design_context
            # Also inject as flat keys for convenience: width, height, etc.
            values.update(design_context)
        return values

    def _eval_quantity_formula(
        self,
        product,
        product_uom,
        product_uom_qty,
        production,
        operation_id=False,
        design_context=None,
    ):
        """Extended formula evaluation with result/product/uom return.

        The formula can assign:
          - ``result`` or ``quantity`` — computed quantity (float)
          - ``product`` — override the BoM line product (recordset)
          - ``uom`` — override the UoM (recordset)

        Returns:
          - dict ``{quantity, product, uom}`` when product or uom changed
          - float (quantity) when only quantity was computed
          - None when no formula is set
        """
        self.ensure_one()
        formula = self.quantity_formula
        if not formula:
            return None

        orig_product_id = product.id
        orig_uom_id = product_uom.id

        values = self._quantity_formula_values(
            product,
            product_uom,
            product_uom_qty,
            production,
            operation_id=operation_id,
            design_context=design_context,
        )
        safe_eval(
            formula,
            globals_dict=values,
            mode="exec",
            nocopy=True,
        )

        # Read result: support both 'result' and 'quantity' variable names
        qty = values.get("result", values.get("quantity", 0))

        # Detect product override (formula wrote: product = env.ref(...))
        ret_product = values.get("product")
        product_changed = (
            ret_product
            and hasattr(ret_product, "id")
            and ret_product.id != orig_product_id
        )

        # Detect UoM override (formula wrote: uom = env.ref(...))
        ret_uom = values.get("uom")
        uom_changed = (
            ret_uom
            and hasattr(ret_uom, "id")
            and ret_uom.id != orig_uom_id
        )

        if product_changed or uom_changed:
            return {
                "quantity": qty,
                "product": ret_product if product_changed else None,
                "uom": ret_uom if uom_changed else None,
            }
        return qty
