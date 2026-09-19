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
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # Движение, добавено от ``add_products`` на формулата. Дели ``bom_line_id``
    # с основното движение на реда, затова ключът му е (ред, продукт), а на
    # основното — (ред, False): така основното остава основно и когато
    # формулата смени продукта му.
    formula_extra = fields.Boolean(
        string="Added by Formula",
        readonly=True,
        help="This component was added by the add_products output of the "
        "quantity formula of its BoM line.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # "formula_skip" и "formula_add_products" са вътрешни маркери на
        # formula evaluation hook-а; стандартната експлозия ги обработва в
        # _get_moves_raw_values, но чужди пътища (напр. Update BoM на жива
        # MO) викат единичния _get_move_raw_values директно — тук маркерите
        # се чистят, за да не стигнат до ORM-а (в тези пътища skip-натият
        # ред остава с количество 0, а add_products не се разгръща).
        for vals in vals_list:
            vals.pop("formula_skip", None)
            vals.pop("formula_add_products", None)
        return super().create(vals_list)

    def _formula_raw_move_key(self):
        """Ключ за съпоставка на суровинно движение с експлозията.

        Основното движение на реда: ``(bom_line_id, False)``; движение от
        ``add_products``: ``(bom_line_id, product_id)``.
        """
        self.ensure_one()
        return (
            self.bom_line_id.id,
            self.product_id.id if self.formula_extra else False,
        )
