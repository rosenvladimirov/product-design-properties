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

        return self.create(
            {
                "name": self._generate_child_lot_name(parent_lot, product),
                "product_id": product.id,
                "company_id": parent_lot.company_id.id,
                "design_param_definition_id": (
                    bom_line.child_definition_id.id
                    if bom_line.child_definition_id
                    else False
                ),
                "design_params": child_params or False,
            }
        )

    @api.model
    def _generate_child_lot_name(self, parent_lot, product):
        return self.env["ir.sequence"].next_by_code("stock.lot.serial") or (
            f"{parent_lot.name}-{product.default_code or product.id}"
        )

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
