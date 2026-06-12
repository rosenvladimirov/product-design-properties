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

    # ── Formula evaluation (собствено ядро, без външни зависимости) ──────

    def _quantity_formula_values(
        self,
        product,
        product_uom,
        product_uom_qty,
        production,
        operation_id=False,
        design_context=None,
    ):
        """Build the evaluation context for a BoM line quantity formula."""
        self.ensure_one()
        # operation_id идва като int (от core _get_moves_raw_values) или recordset
        operation = operation_id or False
        if operation and not hasattr(operation, "_name"):
            operation = self.env["mrp.routing.workcenter"].browse(operation)
        values = {
            "bom_line": self,
            "operation": operation,
            "product": product,
            "product_uom": product_uom,
            "product_uom_qty": product_uom_qty,
            "production": production,
            # начална стойност = стандартното expl. количество;
            # формулата я презаписва (legacy синтаксис `quantity = ...`)
            "quantity": product_uom_qty,
            # Allow formulas to use env.ref(), env['model'].search(), etc.
            "env": self.env,
        }
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
        # Odoo 19: safe_eval(expr, context, mode=...) — context се
        # мутира in-place (няма вече globals_dict/nocopy)
        safe_eval(
            formula,
            values,
            mode="exec",
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
        uom_changed = ret_uom and hasattr(ret_uom, "id") and ret_uom.id != orig_uom_id

        # Detect extra products (formula wrote: add_products = [...])
        extra_products = values.get("add_products")

        if product_changed or uom_changed or extra_products:
            result = {
                "quantity": qty,
                "product": ret_product if product_changed else None,
                "uom": ret_uom if uom_changed else None,
            }
            if extra_products:
                result["add_products"] = extra_products
            return result
        return qty
