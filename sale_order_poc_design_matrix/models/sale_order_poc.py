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
"""POC храни матрицата — едно към едно по име (ADR sale-order-poc/0019).

Код на параметър на POC, равен на името на параметър на матрицата (``string``
в схемата на дизайн дефиницията), го храни. Нищо друго не се пипа: само POC
има своите параметри, само матрицата — своите. Запис (например материал —
вариант на продукт) става суровият ключ на избора в матрицата.

Кога се чете POC: докато дизайн партидата не е фиксирана. При потвърждаване
партидата на POC се ражда и носи параметрите на матрицата — подразбиранията
на дефиницията плюс стойностите от POC; оттам нататък матрицата чете от
партидата, а не от POC.

Модулът НЕ зависи от конфигуратора на продажбата: върви и в завод, който
отваря матрицата само в производството. Кубчето, цената от сухия пробег и
осиновяването на партидата на конфигуратора са в
``sale_order_poc_design_configurator``.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    # ── Контекстът на матрицата ──────────────────────────────────────

    def _poc_matrix_definition(self):
        """Дизайн дефиницията на артикула в реда — или празно.

        С конфигуратора е неговата: същата, която отваря кубчето, с неговия
        филтър по фирма. Без него — дефиницията на артикула, после тази на
        рецептата, по която артикулът ще се произвежда.
        """
        self.ensure_one()
        Definition = self.env["design.param.definition"]
        line = self.sudo().sale_line_id
        product = line.product_id
        if not product:
            return Definition
        if "design_param_definition_id" in line._fields:
            return line.design_param_definition_id
        if (
            "design_param_definition_id" in product._fields
            and product.design_param_definition_id
        ):
            return product.design_param_definition_id
        bom = self.env["mrp.bom"].sudo()._bom_find(product).get(product)
        return bom.design_param_definition_id if bom else Definition

    def _poc_matrix_schema(self, definition):
        """Параметрите на матрицата без разделителите."""
        return [
            prop
            for prop in definition.full_design_params_definition or []
            if isinstance(prop, dict)
            and prop.get("name")
            and prop.get("string")
            and prop.get("type") != "separator"
        ]

    def _poc_matrix_value(self, prop, value):
        """Стойността на POC във вида, който матрицата пази.

        Запис става суровият ключ на избора: името на варианта (стойностите
        на атрибутите му), после името, после показваното име — първото,
        което изборът познава. Запис срещу параметър, който не е избор, няма
        съответствие.
        """
        if not isinstance(value, models.BaseModel):
            return value
        if prop.get("type") != "selection":
            return None
        keys = {str(option[0]) for option in prop.get("selection") or []}
        record = value[:1]
        candidates = []
        if "product_template_attribute_value_ids" in record._fields:
            candidates.append(
                ", ".join(record.product_template_attribute_value_ids.mapped("name"))
            )
        candidates += [record.name, record.display_name]
        return next((c for c in candidates if c in keys), None)

    def _poc_matrix_values(self, schema):
        """{име на параметъра: стойност} за кодовете на POC, които матрицата има."""
        self.ensure_one()
        by_string = {prop["string"]: prop for prop in schema}
        out = {}
        for code, value in self._poc_values().items():
            prop = by_string.get(code)
            # празният запис е „няма стойност“, като None — остава
            # подразбирането на матрицата
            if (
                not prop
                or value is None
                or (isinstance(value, models.BaseModel) and not value)
            ):
                continue
            converted = self._poc_matrix_value(prop, value)
            if converted is None:
                _logger.warning(
                    "POC %s: %r=%r has no match in matrix parameter %s.",
                    self.name,
                    code,
                    value,
                    prop["name"],
                )
                continue
            out[code] = converted
        return out

    def _poc_matrix_context(self):
        """Контекстът на матрицата: нейните подразбирания + стойностите от POC.

        Същият вид като на конфигуратора: ``{име на параметъра: стойност}``.
        ``None`` значи, че артикулът няма дизайн дефиниция.
        """
        self.ensure_one()
        definition = self._poc_matrix_definition()
        if not definition:
            return None
        schema = self._poc_matrix_schema(definition)
        context = {prop["string"]: prop.get("default") for prop in schema}
        context.update(self._poc_matrix_values(schema))
        return context

    # ── Партидата при потвърждаване ──────────────────────────────────

    def _poc_ensure_lot(self):
        res = super()._poc_ensure_lot()
        for poc in self:
            if poc.lot_id:
                poc._poc_matrix_write_params(poc.lot_id)
        return res

    def _poc_matrix_write_params(self, lot):
        """Партидата носи параметрите на матрицата: нейните + тези от POC.

        Партида на същата дефиниция (например осиновена от конфигуратора)
        пази стойностите си; POC пише върху тях само своите.
        """
        self.ensure_one()
        definition = self._poc_matrix_definition()
        if not definition:
            return
        schema = self._poc_matrix_schema(definition)
        current = {}
        if lot.design_param_definition_id == definition:
            # в Python Properties са {UUID: стойност} в `_values`; списъкът с
            # речници е само видът по RPC
            current = dict(lot.design_params._values or {})
        params = {
            prop["name"]: current.get(prop["name"], prop.get("default"))
            for prop in schema
        }
        by_string = {prop["string"]: prop["name"] for prop in schema}
        for string, value in self._poc_matrix_values(schema).items():
            params[by_string[string]] = value
        lot = lot.sudo()
        if lot.design_param_definition_id != definition:
            lot.design_param_definition_id = definition
        lot.design_params = params
