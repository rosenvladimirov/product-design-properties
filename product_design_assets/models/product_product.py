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

    # ── Design parameter definition (dropdown) ───────────────────────
    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Definition",
        help="Select the design parameter set for this product. "
             "Used by the configurator for filtering and PTAV matching.",
    )

    # ── Design properties (dynamic fields from definition) ───────────
    design_properties = fields.Properties(
        "Design Properties",
        definition="design_param_definition_id.full_design_params_definition",
        help="Product-level design properties for configurator filtering. "
             "Values must match product.attribute.value.name for PTAV resolution.",
    )

    # ── Design assets (M2M to ir.attachment) ─────────────────────────
    design_asset_ids = fields.Many2many(
        "ir.attachment",
        "product_design_asset_rel",
        "product_id",
        "attachment_id",
        string="Design Assets",
        help="GLB (3D models), SVG (profiles), PNG/JPG (textures) "
             "for design configurator visualization.",
    )
    design_asset_count = fields.Integer(
        compute="_compute_design_asset_count",
        string="Design Assets",
    )

    def _compute_design_asset_count(self):
        for product in self:
            product.design_asset_count = len(product.design_asset_ids)

    @api.model
    def get_design_assets_by_type(self, product_id):
        """RPC: Returns design assets grouped by type for the JS configurator."""
        product = self.browse(product_id)
        if not product.exists():
            return {"models_3d": [], "profiles_svg": [], "textures": []}

        atts = product.design_asset_ids.read(["id", "name", "mimetype", "file_size"])

        result = {"models_3d": [], "profiles_svg": [], "textures": []}
        for a in atts:
            mime = a.get("mimetype", "")
            if mime == "model/gltf-binary":
                result["models_3d"].append(a)
            elif mime == "image/svg+xml":
                result["profiles_svg"].append(a)
            elif mime in ("image/jpeg", "image/png"):
                result["textures"].append(a)
        return result

    @api.model
    def get_template_variant_assets(self, product_id):
        """RPC: Returns all variants of the same template with PNG/JPG textures.

        Used by the overlay gallery to show all selectable accessory variants.
        """
        product = self.browse(product_id)
        if not product.exists():
            return []
        result = []
        for variant in product.product_tmpl_id.product_variant_ids:
            textures = variant.design_asset_ids.filtered(
                lambda a: a.mimetype in ("image/jpeg", "image/png")
            ).read(["id", "name", "mimetype"])
            if textures:
                ptav_names = variant.product_template_variant_value_ids.mapped(
                    "name"
                )
                result.append({
                    "variant_id": variant.id,
                    "variant_name": variant.display_name,
                    "ptav_name": ptav_names[0] if ptav_names else variant.display_name,
                    "textures": textures,
                })
        return result

    @api.model
    def get_template_variant_all_assets(self, product_id):
        """RPC: Returns all variants with all design assets (GLB + textures).

        Used to swap 3D models when the user changes a variant selection.
        """
        product = self.browse(product_id)
        if not product.exists():
            return []
        result = []
        for variant in product.product_tmpl_id.product_variant_ids:
            assets = self.get_design_assets_by_type(variant.id)
            if any(v for v in assets.values()):
                ptav_names = variant.product_template_variant_value_ids.mapped(
                    "name"
                )
                result.append({
                    "variant_id": variant.id,
                    "variant_name": variant.display_name,
                    "ptav_name": ptav_names[0] if ptav_names else variant.display_name,
                    "assets": assets,
                })
        return result

    def action_view_design_assets(self):
        """Button action to view design asset attachments."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Design Assets",
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.design_asset_ids.ids)],
            "context": {
                "default_res_model": "product.product",
                "default_res_id": self.id,
            },
        }


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ── Delegated fields from product.product ────────────────────────
    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Definition",
        compute="_compute_design_param_definition_id",
        inverse="_inverse_design_param_definition_id",
        search="_search_design_param_definition_id",
    )
    design_properties = fields.Properties(
        "Design Properties",
        compute="_compute_design_properties",
        inverse="_inverse_design_properties",
        definition="design_param_definition_id.full_design_params_definition",
    )

    @api.depends("product_variant_ids", "product_variant_ids.design_param_definition_id")
    def _compute_design_param_definition_id(self):
        for record in self:
            if record.product_variant_ids:
                record.design_param_definition_id = (
                    record.product_variant_ids[0].design_param_definition_id
                )
            else:
                record.design_param_definition_id = False

    def _inverse_design_param_definition_id(self):
        for record in self:
            for product in record.product_variant_ids:
                if product.design_param_definition_id != record.design_param_definition_id:
                    product.write({"design_properties": False})
                product.design_param_definition_id = record.design_param_definition_id

    def _search_design_param_definition_id(self, operator, value):
        product_ids = (
            self.env["product.product"]
            .search([("design_param_definition_id", operator, value)])
            .mapped("product_tmpl_id")
            .ids
        )
        return [("id", "in", product_ids)]

    @api.depends("product_variant_ids.design_properties")
    def _compute_design_properties(self):
        for record in self:
            if record.product_variant_ids:
                record.design_properties = record.product_variant_ids[0].design_properties
            else:
                record.design_properties = False

    def _inverse_design_properties(self):
        for record in self:
            if record.product_variant_count == 1 and record.design_properties:
                for product in record.product_variant_ids.filtered(
                    lambda p: p.design_properties != record.design_properties
                ):
                    product.write({"design_properties": record.design_properties})
