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
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Каноничното (formula_name) име на параметъра, който носи префикса за
# лотовете. Резолвва се през слития param_dictionary — етикетът и uuid-ът
# на property-то могат да се сменят, каноничното име е стабилният ключ.
LOT_PREFIX_PARAM = "lot_prefix"

# Стойността може да е ШАБЛОН по комбинацията ("{series}{lock_points}"),
# а не готов префикс. Такъв шаблон НЕ отива в полето на шаблона —
# резолвва се на партида, защото всяка комбинация иска своя поредица.
LOT_PREFIX_PLACEHOLDER = "{"

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

    # ── Lot prefix, carried by the design properties ─────────────────
    # Механиката на партидите НЕ се пипа: Odoo сама решава името
    # (`stock.lot._compute_name` от `product_id.lot_sequence_id`) и сама
    # намира или създава последователността (`_inverse_serial_prefix_format`).
    # Тук се решава САМО кой е префиксът — за да не се задава на ръка по
    # хиляди шаблона, когато дизайн параметрите вече го знаят.

    def _design_lot_prefix(self):
        """Return the raw lot prefix value from this product's design properties.

        The value is either a ready prefix ("Б") or a template resolved per
        combination ("{series}{lock_points}") — see
        ``_design_lot_prefix_is_template``.
        """
        self.ensure_one()
        definition = self.design_param_definition_id
        if not definition:
            return ""
        entry = (definition._get_merged_param_dictionary() or {}).get(LOT_PREFIX_PARAM)
        uuid = entry.get("uuid") if isinstance(entry, dict) else None
        if not uuid:
            return ""
        # 🚨 Properties: празна и нулева стойност се четат като False, не като
        # "" / 0 — затова стойността се нормализира изрично, вместо да се
        # разчита на falsy сравнение.
        value = (self.design_properties or {}).get(uuid)
        return str(value).strip() if value else ""

    def _design_lot_prefix_is_template(self):
        """Whether the prefix has to be resolved against a combination."""
        self.ensure_one()
        return LOT_PREFIX_PLACEHOLDER in self._design_lot_prefix()

    def _sync_design_lot_prefix(self):
        """Push a ready design prefix onto ``product.template.serial_prefix_format``.

        The core inverse of that field reuses the existing sequence for the
        prefix or creates a new one, so nothing here generates names or
        sequences. Two cases are deliberately skipped:

        * a prefix template — one sequence per template could not serve the
          many prefixes a matrix produces, so it is resolved per combination
          when the lot is created;
        * variants of one template asking for different ready prefixes — a
          template carries a single sequence, and guessing a winner would
          silently renumber a range.
        """
        # Само продуктите с дизайн дефиниция могат да носят префикс —
        # филтърът пази `create` на всеки обикновен вариант от обхождане.
        for template in self.filtered("design_param_definition_id").mapped(
            "product_tmpl_id"
        ):
            prefixes = {
                prefix
                for prefix in (
                    variant._design_lot_prefix()
                    for variant in template.product_variant_ids
                )
                if prefix and LOT_PREFIX_PLACEHOLDER not in prefix
            }
            if not prefixes:
                continue
            if len(prefixes) > 1:
                # Не се гадае кой префикс печели — шаблонът има само една
                # последователност, а разминаването е конфигурационен въпрос.
                _logger.warning(
                    "Product template %s: variants ask for %d different lot "
                    "prefixes (%s). Odoo keeps one sequence per template, so "
                    "the prefix is left unchanged.",
                    template.display_name,
                    len(prefixes),
                    ", ".join(sorted(prefixes)),
                )
                continue
            prefix = prefixes.pop()
            if template.serial_prefix_format != prefix:
                template.serial_prefix_format = prefix

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._sync_design_lot_prefix()
        return products

    def write(self, vals):
        res = super().write(vals)
        if {"design_properties", "design_param_definition_id"} & set(vals):
            self._sync_design_lot_prefix()
        return res

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
                ptav_names = variant.product_template_variant_value_ids.mapped("name")
                result.append(
                    {
                        "variant_id": variant.id,
                        "variant_name": variant.display_name,
                        "ptav_name": ptav_names[0]
                        if ptav_names
                        else variant.display_name,
                        "textures": textures,
                    }
                )
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
                ptav_names = variant.product_template_variant_value_ids.mapped("name")
                result.append(
                    {
                        "variant_id": variant.id,
                        "variant_name": variant.display_name,
                        "ptav_name": ptav_names[0]
                        if ptav_names
                        else variant.display_name,
                        "assets": assets,
                    }
                )
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
        compute="_compute_design_properties",
        inverse="_inverse_design_properties",
        definition="design_param_definition_id.full_design_params_definition",
    )

    @api.depends(
        "product_variant_ids",
        "product_variant_ids.design_param_definition_id",
    )
    def _compute_design_param_definition_id(self):
        for record in self:
            if record.product_variant_ids:
                record.design_param_definition_id = record.product_variant_ids[
                    0
                ].design_param_definition_id
            else:
                record.design_param_definition_id = False

    def _inverse_design_param_definition_id(self):
        for record in self:
            for product in record.product_variant_ids:
                if (
                    product.design_param_definition_id
                    != record.design_param_definition_id
                ):
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
                record.design_properties = record.product_variant_ids[
                    0
                ].design_properties
            else:
                record.design_properties = False

    def _inverse_design_properties(self):
        for record in self:
            if record.product_variant_count == 1 and record.design_properties:
                new_props = record.design_properties
                for product in record.product_variant_ids.filtered(
                    lambda p, new_props=new_props: p.design_properties != new_props
                ):
                    product.write({"design_properties": new_props})
