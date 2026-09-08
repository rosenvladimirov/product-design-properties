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
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    # width / height / thickness come from stock_move_forced_lot_multi_dim

    # Явни избори на материал от конфигуратора: {"choice_<key>": product_id}.
    # Пазят се отделно от design_params (Properties би изхвърлило ключове
    # извън дефиницията).
    matrix_material_choices = fields.Json("Material Choices")
    # Избрани операции от конфигуратора: списък mrp.workcenter id.
    matrix_operation_choices = fields.Json("Operation Choices")
    # Избрани атрибути на полуфабрикатите (крило/каса/лайсна): цвят/покритие/
    # материал/мотив. Формат {"cattr_<bomLineId>_<attrId>": <ptav_id>}.
    # Матрицата суапва placeholder-компонента към конкретния вариант.
    matrix_component_attrs = fields.Json("Component Attributes")

    # ── helpers ──────────────────────────────────────────────────────────

    def _get_design_context(self) -> dict:
        """
        Return a flat dict suitable for GoRules / formula evaluation.

        Three decoupled name layers feed the same flat context, so a formula
        resolves no matter which name it uses:
          - **formula_name** (canonical, snake_case ASCII) — the стабилен
            идентификатор; the preferred thing formulas read. Built from the
            definition's ``param_dictionary`` (merged along the parent chain,
            so a client overlay inherits the vertical's canon).
          - **string** (display label) — kept for backward compatibility with
            formulas authored before the canon (e.g. ``main_lock`` already, or
            legacy ``Основна``).
          - **legacy aliases** (``c_*`` / Cyrillic display) — expanded to the
            canonical value via ``legacy_aliases`` so 2 393 legacy formulas
            keep working WITHOUT being rewritten.
        Selection display labels are reversed to raw values (e.g. "Vinegar
        Brine" → "vinegar") so rule conditions match what is stored.
        """
        self.ensure_one()
        # Един резолвер за lot и MO — виж design.param.definition._build_context.
        return self.design_param_definition_id._build_context(
            self.design_params,
            {
                "width": getattr(self, "width", 0.0),
                "height": getattr(self, "height", 0.0),
                "thickness": getattr(self, "thickness", 0.0),
                "material_choices": self.matrix_material_choices or {},
            },
        )

    # ── Lot name from the combination ────────────────────────────────
    # Odoo names lots itself (`stock.lot._compute_name` from
    # `product_id.lot_sequence_id`) and finds or creates the sequence for a
    # prefix itself (the inverse of `product.template.serial_prefix_format`).
    # Един шаблон обаче носи ЕДНА последователност, а матрицата произвежда
    # много префикса от една номенклатура. Затова тук се резолвва префиксът
    # НА КОМБИНАЦИЯТА и всяка нова комбинация получава своята поредица —
    # по същия договор като ядрото, не по втори механизъм.

    @api.model
    def _format_lot_prefix(self, prefix_template, context):
        """Resolve a prefix template ("{series}{lock_points}") to a prefix."""
        # None в контекста би влязло в номера като "None" — по-добре празно.
        safe_context = {
            key: ("" if value is None else value)
            for key, value in (context or {}).items()
        }
        try:
            prefix = prefix_template.format_map(safe_context)
        except (KeyError, IndexError, ValueError) as exc:
            # Не се мълчи и не се ражда сгрешен префикс: партидата ще получи
            # стандартен номер, а причината стои в лога с името на параметъра.
            _logger.warning(
                "Lot prefix template %r cannot be resolved (%s); "
                "the lot falls back to the product sequence.",
                prefix_template,
                exc,
            )
            return ""
        prefix = prefix.strip()
        if "%" in prefix:
            # 🚨 ir.sequence интерполира `%(...)s` в префикса — символът от
            # параметър би счупил всяко следващо взимане на номер.
            _logger.warning(
                "Lot prefix %r contains '%%', which ir.sequence interpolates; "
                "the lot falls back to the product sequence.",
                prefix,
            )
            return ""
        return prefix

    @api.model
    def _find_or_create_lot_sequence(self, prefix):
        """Find, or create, the sequence serving *prefix*.

        Same contract as the core inverse of
        ``product.template.serial_prefix_format``: the lookup is by prefix
        ALONE, and a new sequence is created with code ``stock.lot.serial``,
        padding 7 and no company. Narrowing the lookup would create a second
        sequence for a prefix the core already serves, and both sides would
        then hand out the same numbers.
        """
        sequence = self.env["ir.sequence"].search([("prefix", "=", prefix)], limit=1)
        if sequence:
            return sequence
        return self.env["ir.sequence"].create(
            {
                "name": f"{prefix} Lot Sequence",
                "code": "stock.lot.serial",
                "prefix": prefix,
                "padding": 7,
                "company_id": False,
            }
        )

    @api.model
    def _design_lot_name_from_combination(self, vals):
        """Name for a new lot whose product carries a prefix TEMPLATE.

        Returns an empty string when the combination does not decide the
        name — a ready prefix is already served by the product's own
        sequence, so Odoo handles it and nothing is done here.
        """
        product = self.env["product.product"].browse(vals.get("product_id"))
        # Soft-check: двигателят не зависи от product_design_assets.
        if not product or not hasattr(product, "_design_lot_prefix"):
            return ""
        prefix_template = product._design_lot_prefix()
        if not prefix_template or "{" not in prefix_template:
            return ""
        definition = self.env["design.param.definition"].browse(
            vals.get("design_param_definition_id")
        )
        if not definition:
            definition = product.design_param_definition_id
        context = definition._build_context(
            vals.get("design_params") or {},
            {
                "width": vals.get("width") or 0.0,
                "height": vals.get("height") or 0.0,
                "thickness": vals.get("thickness") or 0.0,
                "material_choices": vals.get("matrix_material_choices") or {},
            },
        )
        prefix = self._format_lot_prefix(prefix_template, context)
        if not prefix:
            return ""
        return self._find_or_create_lot_sequence(prefix).next_by_id() or ""

    @api.model_create_multi
    def create(self, vals_list):
        # 🚨 `product_category_lot_sequence` има СВОЙ create, който също пише
        # `name` за партида без име. Приоритетът „комбинация бие категория“
        # излиза от реда на зареждане (то зависи само от `stock`, значи е
        # по-малко производно и получава vals ПОСЛЕ нас) — тоест виси на
        # зависимостите, не на явен избор. Заковано е с тест
        # (test_combination_wins_over_category_sequence); ако някой обърне
        # реда, тестът пада, вместо номерата да се сменят тихо.
        for vals in vals_list:
            if not vals.get("name"):
                name = self._design_lot_name_from_combination(vals)
                if name:
                    vals["name"] = name
        return super().create(vals_list)

    @api.model
    def _create_child_lot(self, parent_lot, bom_line, product):
        """
        Create a child lot for a semi-finished product by extracting
        parameters from *parent_lot* according to *bom_line.param_extraction_map*.

        :param parent_lot:  ``stock.lot`` of the parent MO product.
        :param bom_line:    ``mrp.bom.line`` with ``param_extraction_map``
                            and ``child_definition_id`` set.
        :param product:     ``product.product`` for the child lot.
        :returns:           Newly created ``stock.lot``.
        """
        param_map = bom_line.param_extraction_map or {}
        parent_ctx = parent_lot._get_design_context()
        child_params = {}

        for child_key, source in param_map.items():
            if source in parent_ctx:
                # Direct copy
                child_params[child_key] = parent_ctx[source]
            else:
                # Formula — safe_eval against parent context
                try:
                    child_params[child_key] = safe_eval(source, parent_ctx)
                except Exception as e:
                    _logger.warning(
                        "Param extraction failed for %s = %r: %s",
                        child_key,
                        source,
                        e,
                    )
                    child_params[child_key] = None

        child_vals = {
            "product_id": product.id,
            "company_id": parent_lot.company_id.id,
            "design_param_definition_id": (
                bom_line.child_definition_id.id
                if bom_line.child_definition_id
                else False
            ),
            "design_params": child_params or False,
        }
        # Името се оставя на Odoo (или на комбинацията) — явното име по-рано
        # заобикаляше и двете. Пази се само случаят, в който продуктът няма
        # НИКАКВА последователност: тогава core-ският compute би оставил
        # задължителното поле празно.
        if not product.lot_sequence_id:
            child_vals["name"] = self._generate_child_lot_name(parent_lot, product)
        return self.create(child_vals)

    @api.model
    def _generate_child_lot_name(self, parent_lot, product):
        """Last-resort name for a child lot of a product with no sequence.

        🚨 The previous ``next_by_code("stock.lot.serial")`` is deliberately
        gone: the core inverse of ``serial_prefix_format`` creates one record
        with that very code per prefix, so a lookup by code alone got less
        predictable with every prefix anyone added.
        """
        return f"{parent_lot.name}-{product.default_code or product.id}"

    def _find_matching_stock_lot(self, product, required_params: dict):
        """
        Find an existing lot whose ``design_params`` match *required_params*.

        Used when ``mto_stop=True`` on a BoM line — the system looks for
        stock instead of triggering a new MO.

        :returns: matching ``stock.lot`` or empty recordset.
        """
        candidates = self.search(
            [
                ("product_id", "=", product.id),
                ("design_param_definition_id", "!=", False),
            ]
        )
        for lot in candidates:
            lot_params = dict(lot.design_params or {})
            if all(lot_params.get(k) == v for k, v in required_params.items()):
                return lot
        return self.browse()
