# Copyright 2026 Rosen Vladimirov
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


class MrpBomLine(models.Model):
    """Stage 2: количествата на суровините по конфигурацията.

    Договорът е ИЗРИЧЕН (ADR sale-order-poc/0005): стойностите на POC по
    кодовете им плюс производственият контекст, без нито един базов ключ на
    PDP. Кодовете на речника не могат да се казват като тях (речникът пази
    POC_RESERVED_NAMES), затова засенчване няма.
    """

    _inherit = "mrp.bom.line"

    def _quantity_formula_values(
        self,
        product,
        product_uom,
        product_uom_qty,
        production,
        operation_id=False,
        design_context=None,
    ):
        values = super()._quantity_formula_values(
            product,
            product_uom,
            product_uom_qty,
            production,
            operation_id=operation_id,
            design_context=design_context,
        )
        poc = production.poc_id if production else False
        if not poc:
            return values
        contract = production._poc_formula_context()
        clash = sorted(set(contract) & set(values))
        if clash:
            # базовият ключ на PDP печели; случи ли се, речникът е пуснал
            # запазено име и това е дефект, не потребителска грешка
            _logger.error(
                "sale_order_poc: %s shadows the base keys of the formula "
                "engine: %s",
                poc.display_name,
                ", ".join(clash),
            )
        values.update(
            {code: value for code, value in contract.items() if code not in values}
        )
        return values
