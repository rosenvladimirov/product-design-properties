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
from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # -- Design lot linked to this SO line -----------------------------------
    design_lot_id = fields.Many2one(
        "stock.lot",
        string="Design Lot",
        copy=False,
        help=(
            "The design lot carrying the customer-specific parameters "
            "for this line. Created via the Design Configurator."
        ),
    )

    # -- Computed: does the selected product have a design definition? --------
    has_design_definition = fields.Boolean(
        compute="_compute_has_design_definition",
        store=False,
    )
    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        compute="_compute_has_design_definition",
        store=False,
        string="Design Parameter Set",
    )

    # -- Summary shown on the SO line (read-only) ----------------------------
    design_params_summary = fields.Char(
        compute="_compute_design_params_summary",
        string="Design Parameters",
        store=False,
    )

    # -- Computed fields -----------------------------------------------------

    @api.depends("product_id")
    def _compute_has_design_definition(self):
        """
        Find design definition for the product. Search order:
        1. product.product.design_param_definition_id (direct on product)
        2. mrp.bom.design_param_definition_id (from BoM)
        Filtered by company active definitions if configured.
        """
        for line in self:
            if not line.product_id:
                line.has_design_definition = False
                line.design_param_definition_id = False
                continue

            active_defs = self.env.company.design_definition_ids
            found = False

            # 1. Check product.product directly
            prod_def = line.product_id.design_param_definition_id
            if prod_def:
                if not active_defs or prod_def in active_defs:
                    line.has_design_definition = True
                    line.design_param_definition_id = prod_def
                    found = True

            # 2. Fallback: check BoM
            if not found:
                domain = [
                    ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                    ("design_param_definition_id", "!=", False),
                    ("active", "=", True),
                ]
                if active_defs:
                    domain.append(("design_param_definition_id", "in", active_defs.ids))
                bom = self.env["mrp.bom"].search(domain, limit=1)
                if bom:
                    line.has_design_definition = True
                    line.design_param_definition_id = bom.design_param_definition_id
                    found = True

            if not found:
                line.has_design_definition = False
                line.design_param_definition_id = False

    @api.depends("design_lot_id", "design_lot_id.design_params")
    def _compute_design_params_summary(self):
        """\u0420\u0435\u0437\u044e\u043c\u0435 \u043d\u0430 \u0440\u0435\u0434\u0430 \u0441 \u0427\u041e\u0412\u0415\u0428\u041a\u0418 \u0438\u043c\u0435\u043d\u0430, \u043d\u0435 \u0441 Property UUID-\u0442\u0430.

        ``design_params`` \u0435 \u043a\u043b\u044e\u0447\u0438\u0440\u0430\u043d \u043f\u043e UUID \u2014 \u043f\u0435\u0447\u0430\u0442\u0430\u043d \u0441\u0443\u0440\u043e\u0432, \u0440\u0435\u0434\u044a\u0442
        \u0438\u0437\u0433\u043b\u0435\u0436\u0434\u0430\u0448\u0435 \u043a\u0430\u0442\u043e ``0e4920bfb6318e39: 1600.0``, \u043a\u043e\u0435\u0442\u043e \u043d\u0435 \u043a\u0430\u0437\u0432\u0430 \u043d\u0438\u0449\u043e
        \u043d\u0430 \u0442\u044a\u0440\u0433\u043e\u0432\u0435\u0446\u0430. \u0421\u0445\u0435\u043c\u0430\u0442\u0430 \u043d\u0430 \u0434\u0435\u0444\u0438\u043d\u0438\u0446\u0438\u044f\u0442\u0430 \u043d\u043e\u0441\u0438 ``string`` (\u0435\u0442\u0438\u043a\u0435\u0442\u0430) \u0438
        ``selection`` (\u0434\u0432\u043e\u0439\u043a\u0438\u0442\u0435 \u0441\u0442\u043e\u0439\u043d\u043e\u0441\u0442/\u0435\u0442\u0438\u043a\u0435\u0442), \u0437\u0430\u0442\u043e\u0432\u0430 \u0440\u0435\u0437\u043e\u043b\u0432\u0430\u043c\u0435 \u0438
        \u0434\u0432\u0435\u0442\u0435. \u0421\u0445\u0435\u043c\u0430\u0442\u0430 \u0441\u0435 \u0447\u0435\u0442\u0435 \u043f\u043e \u0432\u0435\u0434\u043d\u044a\u0436 \u043d\u0430 \u0434\u0435\u0444\u0438\u043d\u0438\u0446\u0438\u044f, \u043d\u0435 \u043d\u0430 \u0440\u0435\u0434.
        """
        schema_cache = {}

        def schema_for(definition):
            if definition.id not in schema_cache:
                labels, choices, order = {}, {}, {}
                # Редът на реда се определя от param_levels, а не от позицията
                # в схемата. Схемата е „родителска верига + собствени", тоест
                # най-общото стои отпред: за кашон това изкарваше размерите на
                # врата (900×2100×40, наследени от base_dimensions) пред типа
                # вълна. Нивото казва кое КОЙ вижда — редът на офертата е на
                # търговеца, затова sales параметрите вървят първи.
                # Нивата се мърджват по родителската верига както
                # param_dictionary и legacy_aliases: размерите на кашона
                # живеят в родителската дефиниция, печатът — в детето, а
                # редът на офертата ги показва заедно.
                levels = {}
                for defn in reversed(definition._chain_bottom_up()):
                    if defn.param_levels:
                        levels.update(defn.param_levels)
                rank = {"sales": 0, "technical": 1, "production": 2}
                for pos, prop in enumerate(
                        definition.full_design_params_definition or []):
                    if not isinstance(prop, dict) or not prop.get("name"):
                        continue
                    uuid = prop["name"]
                    label = prop.get("string") or uuid
                    labels[uuid] = label
                    # param_levels е ключиран по етикета, не по UUID.
                    lvl = levels.get(label) or levels.get(uuid)
                    order[uuid] = rank.get(lvl, 3) * 10 ** 4 + pos
                    choices[uuid] = {
                        str(raw): label
                        for entry in (prop.get("selection") or [])
                        if isinstance(entry, (list, tuple)) and len(entry) == 2
                        for raw, label in [entry]
                    }
                schema_cache[definition.id] = (labels, choices, order)
            return schema_cache[definition.id]

        for line in self:
            lot = line.design_lot_id
            if not lot or not lot.design_params:
                line.design_params_summary = ""
                continue
            labels, choices, order = ({}, {}, {})
            if lot.design_param_definition_id:
                labels, choices, order = schema_for(lot.design_param_definition_id)
            parts = []
            for key, value in (lot.design_params or {}).items():
                if value in (None, False, ""):
                    continue
                name = labels.get(key, key)
                shown = choices.get(key, {}).get(str(value), value)
                # \u0420\u0435\u0434\u044a\u0442 \u0435 \u0442\u043e\u0437\u0438 \u043e\u0442 \u0434\u0435\u0444\u0438\u043d\u0438\u0446\u0438\u044f\u0442\u0430, \u043d\u0435 \u0430\u0437\u0431\u0443\u0447\u0435\u043d: \u0441\u043f\u0435\u0446\u0438\u0444\u0438\u0447\u043d\u0438\u0442\u0435 \u0437\u0430
                # \u0438\u0437\u0434\u0435\u043b\u0438\u0435\u0442\u043e \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u0438 \u0441\u0442\u043e\u044f\u0442 \u043f\u0440\u0435\u0434 \u043d\u0430\u0441\u043b\u0435\u0434\u0435\u043d\u0438\u0442\u0435 \u043e\u0442 \u0440\u043e\u0434\u0438\u0442\u0435\u043b\u044f,
                # \u0442\u0430\u043a\u0430 \u0447\u0435 \u043e\u0442\u0440\u044f\u0437\u0432\u0430\u043d\u0435\u0442\u043e \u0434\u043e \u0448\u0435\u0441\u0442 \u043f\u043e\u043a\u0430\u0437\u0432\u0430 \u043a\u0430\u043a\u0432\u043e\u0442\u043e \u0438\u043c\u0430 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435.
                parts.append((order.get(key, 10 ** 6), f"{name}: {shown}"))
            line.design_params_summary = "  \u00b7  ".join(
                text for _, text in sorted(parts, key=lambda p: p[0])[:6])

    # -- Onchange: reset design lot when product changes ---------------------

    @api.onchange("product_id")
    def _onchange_product_id_reset_design_lot(self):
        """Clear the design lot when the product changes."""
        self.design_lot_id = False

    # -- Action: open configurator dialog ------------------------------------

    def action_open_design_configurator(self):
        """
        Called from the 'Configure' button on the SO line.
        Returns a client action that opens DesignConfiguratorDialog.
        On lot creation, the lot is written back to this line via
        the JS callback -> Python RPC.
        """
        self.ensure_one()
        if not self.has_design_definition:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No design definition"),
                    "message": _(
                        "The product '%s' has no BoM with a design "
                        "parameter definition."
                    )
                    % self.product_id.display_name,
                    "type": "warning",
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": (
                    self.design_lot_id.id if self.design_lot_id else False
                ),
                # Pass the SO line so the JS callback can write back
                "solId": self.id,
                # Sales level: show only sales params (with images/3D).
                "level": "sales",
            },
        }

    def get_t0_validation_data(self):
        """
        RPC target for the inline T0 widget on SO lines.
        Returns the lot's design params and the BoM's constraint table.
        """
        self.ensure_one()
        if not self.design_lot_id:
            return False
        lot = self.design_lot_id
        # Build params from lot
        if hasattr(lot, "_get_design_context"):
            params = lot._get_design_context()
        else:
            params = dict(lot.design_params or {})
        # Find BoM with constraint_table
        bom_fields = self.env["mrp.bom"]._fields
        if "constraint_table" not in bom_fields:
            return False
        bom = self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.product_id.product_tmpl_id.id),
                ("constraint_table", "!=", False),
            ],
            limit=1,
        )
        if not bom:
            return False
        # Inject variant attribute values via variant_context_map
        if hasattr(bom, "variant_context_map") and bom.variant_context_map:
            for ctx_key, attr_name in bom.variant_context_map.items():
                # Запазеното поле, не `…variant_value_ids` — то изрязва линиите
                # с една стойност (виж _get_variant_context_values в двигателя).
                # Иначе конфигураторът и производството виждат РАЗЛИЧЕН контекст.
                for ptav in self.product_id.product_template_attribute_value_ids:
                    if ptav.attribute_id.name == attr_name:
                        params[ctx_key] = ptav.name
                        break
        return {
            "params": params,
            "constraintTable": bom._translated_constraint_table()
            if hasattr(bom, "_translated_constraint_table")
            else bom.constraint_table,
        }

    def set_design_lot(self, lot_id):
        """
        RPC target called by the JS configurator after lot creation.
        Writes design_lot_id on this line.
        """
        self.ensure_one()
        self.design_lot_id = lot_id
        return True

    @api.model
    def get_design_definition_for_product(self, product_id):
        """
        Lightweight RPC called by the OWL SaleOrderLineProductField patch
        immediately after product selection.

        Search order:
        1. product.product.design_param_definition_id (direct on product)
        2. mrp.bom.design_param_definition_id (from BoM)

        Returns::

            {"definitionId": int, "definitionCode": str}  if found
            False                                          if not found
        """
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return False

        active_defs = self.env.company.design_definition_ids

        # 1. Check product directly
        prod_def = product.design_param_definition_id
        if prod_def and (not active_defs or prod_def in active_defs):
            return {
                "definitionId": prod_def.id,
                "definitionCode": prod_def.code,
            }

        # 2. Fallback: check BoM
        domain = [
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ("design_param_definition_id", "!=", False),
            ("active", "=", True),
        ]
        if active_defs:
            domain.append(("design_param_definition_id", "in", active_defs.ids))
        bom = self.env["mrp.bom"].search(domain, limit=1)
        if not bom:
            return False

        return {
            "definitionId": bom.design_param_definition_id.id,
            "definitionCode": bom.design_param_definition_id.code,
        }

    # -- Propagation to MO: pass design lot through procurement --------------

    def _prepare_procurement_values(self):
        # Odoo 19: базовата сигнатура вече не приема group_id (групата идва от
        # procurement_group_id), затова викаме super() без аргументи.
        vals = super()._prepare_procurement_values()
        if self.design_lot_id:
            vals["design_lot_id"] = self.design_lot_id.id
        return vals
