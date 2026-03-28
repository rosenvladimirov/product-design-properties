# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    @api.model
    def get_bom_design_assets(self, bom_id):
        """RPC: For each BoM line, returns product_id + its design assets.

        Returns list of:
        {
            "product_id": int,
            "product_name": str,
            "bom_line_id": int,
            "assets": {"models_3d": [...], "profiles_svg": [...], "textures": [...]}
        }
        """
        bom = self.browse(bom_id)
        if not bom.exists():
            return []

        result = []
        Product = self.env["product.product"]
        for line in bom.bom_line_ids:
            product = line.product_id
            assets = Product.get_design_assets_by_type(product.id)
            if any(v for v in assets.values()):
                result.append({
                    "product_id": product.id,
                    "product_name": product.display_name,
                    "bom_line_id": line.id,
                    "assets": assets,
                })
        return result
