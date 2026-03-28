# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

DESIGN_MIMETYPES = [
    "model/gltf-binary",
    "image/svg+xml",
    "image/jpeg",
    "image/png",
    "image/vnd.dxf",
]


class ProductProduct(models.Model):
    _inherit = "product.product"

    design_asset_count = fields.Integer(
        compute="_compute_design_asset_count",
        string="Design Assets",
    )

    def _compute_design_asset_count(self):
        Att = self.env["ir.attachment"]
        for product in self:
            product.design_asset_count = Att.search_count([
                ("res_model", "=", "product.product"),
                ("res_id", "=", product.id),
                ("mimetype", "in", DESIGN_MIMETYPES),
            ])

    @api.model
    def get_design_assets_by_type(self, product_id):
        """RPC: Returns design assets grouped by type for the JS configurator.

        Returns dict with keys: models_3d, profiles_svg, textures
        Each value is a list of {id, name, mimetype, file_size}
        """
        product = self.browse(product_id)
        if not product.exists():
            return {"models_3d": [], "profiles_svg": [], "textures": []}

        Att = self.env["ir.attachment"]
        atts = Att.search_read([
            ("res_model", "=", "product.product"),
            ("res_id", "=", product_id),
            ("mimetype", "in", DESIGN_MIMETYPES),
        ], ["id", "name", "mimetype", "file_size"])

        result = {"models_3d": [], "profiles_svg": [], "textures": []}
        for a in atts:
            if a["mimetype"] == "model/gltf-binary":
                result["models_3d"].append(a)
            elif a["mimetype"] == "image/svg+xml":
                result["profiles_svg"].append(a)
            elif a["mimetype"] in ("image/jpeg", "image/png"):
                result["textures"].append(a)
        return result

    def action_view_design_assets(self):
        """Button action to view design asset attachments."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Design Assets",
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [
                ("res_model", "=", "product.product"),
                ("res_id", "=", self.id),
                ("mimetype", "in", DESIGN_MIMETYPES),
            ],
            "context": {
                "default_res_model": "product.product",
                "default_res_id": self.id,
            },
        }
