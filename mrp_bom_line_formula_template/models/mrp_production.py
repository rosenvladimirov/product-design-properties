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

from odoo import models

_logger = logging.getLogger(__name__)


class MRPProduction(models.Model):
    _inherit = "mrp.production"

    def _get_move_raw_values(
        self,
        product,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        """Evaluate the BoM line quantity formula when building raw moves.

        За линия с непразна формула: вика ``_eval_quantity_formula`` и
        прилага резултата върху move стойностите. Float резултат сменя
        само количеството; dict резултат може да override-не и
        product/uom. При грешка или невалиден резултат остава
        стандартното количество от експлозията (+ warning в лога).
        """
        values = super()._get_move_raw_values(
            product,
            product_uom_qty,
            product_uom,
            operation_id=operation_id,
            bom_line=bom_line,
        )
        if not bom_line or not getattr(bom_line, "quantity_formula", False):
            return values

        try:
            result = bom_line._eval_quantity_formula(
                product,
                product_uom,
                product_uom_qty,
                self,
                operation_id=operation_id,
            )
        except Exception:
            _logger.warning(
                "Quantity formula of BoM line %s (product %s) failed; "
                "falling back to the standard exploded quantity.",
                bom_line.id,
                product.display_name,
                exc_info=True,
            )
            return values

        if result is None:
            return values

        if isinstance(result, dict):
            if result.get("skip"):
                # формулата каза "махни реда": маркер за _get_moves_raw_values;
                # stock.move.create също го чисти (за чужди пътища)
                values["formula_skip"] = True
                values["product_uom_qty"] = 0.0
                return values
            try:
                values["product_uom_qty"] = float(result.get("quantity") or 0.0)
            except (TypeError, ValueError):
                _logger.warning(
                    "Quantity formula of BoM line %s returned a non-numeric "
                    "quantity (%r); falling back to the standard quantity.",
                    bom_line.id,
                    result.get("quantity"),
                )
                return values
            if result.get("product"):
                override = result["product"]
                values["product_id"] = override.id
                values["name"] = override.display_name
            if result.get("uom"):
                values["product_uom"] = result["uom"].id
            return values

        try:
            values["product_uom_qty"] = float(result)
        except (TypeError, ValueError):
            _logger.warning(
                "Quantity formula of BoM line %s returned a non-numeric "
                "result (%r); falling back to the standard quantity.",
                bom_line.id,
                result,
            )
        return values

    def _get_moves_raw_values(self):
        """Филтрира редовете, които формулата е маркирала със skip=True.

        Единичният ``_get_move_raw_values`` няма как да каже "пропусни ме",
        затова слага маркер ``formula_skip``; тук (стандартната експлозия)
        маркираните стойности отпадат изцяло — компонентът не се появява
        в MO-то.
        """
        return [
            vals
            for vals in super()._get_moves_raw_values()
            if not vals.pop("formula_skip", False)
        ]
