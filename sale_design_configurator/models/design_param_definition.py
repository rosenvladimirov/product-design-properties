# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class DesignParamDefinition(models.Model):
    _inherit = "design.param.definition"

    @api.depends(
        "parent_id",
        "design_params_definition",
        "parent_id.design_params_definition",
    )
    def _compute_full_design_params_definition(self):
        """Extend: merge child component definitions from BoM products.

        After merging the parent chain (base → industry), also include
        properties from BoM component products that have their own
        design_param_definition_id (e.g., door leaf Slab Type).
        """
        # Let base compute do the parent chain merge first
        super()._compute_full_design_params_definition()

        BomObj = self.env.get("mrp.bom")
        if BomObj is None:
            return  # MRP not installed

        ProductObj = self.env["product.product"]

        for record in self:
            merged = list(record.full_design_params_definition or [])
            seen = {p.get("string") for p in merged}

            # Find products using this definition
            products = ProductObj.search(
                [("design_param_definition_id", "=", record.id)], limit=10
            )
            for product in products:
                boms = BomObj.search(
                    [
                        (
                            "product_tmpl_id",
                            "=",
                            product.product_tmpl_id.id,
                        ),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                for bom in boms:
                    for line in bom.bom_line_ids:
                        child_product = line.product_id
                        child_def = child_product.design_param_definition_id
                        if not child_def or child_def == record:
                            continue
                        for prop in child_def.full_design_params_definition or []:
                            prop_string = prop.get("string", "")
                            if prop_string and prop_string not in seen:
                                merged.append(prop)
                                seen.add(prop_string)
                    break  # One BoM per product is enough

            record.full_design_params_definition = merged
