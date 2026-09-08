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

DESIGN_STATE = [
    ("draft", "Draft"),
    ("sales_confirmed", "Sales Confirmed"),
    ("technical_confirmed", "Technical Confirmed"),
]


class StockLot(models.Model):
    _inherit = "stock.lot"

    # -- Design workflow stage (sales -> technical -> production) -------------
    design_state = fields.Selection(
        DESIGN_STATE,
        string="Design Stage",
        default="draft",
        copy=False,
        index=True,
        help="Workflow stage of the design lot. Sales fills the sales-level "
        "parameters and confirms (locking them); the technical person fills "
        "the technical-level parameters on a tablet and confirms, releasing "
        "the lot to production. Levels come from the definition's param_levels.",
    )

    # -- Workflow transitions ------------------------------------------------

    def action_design_sales_confirm(self):
        """Sales confirms: lock sales-level parameters, hand over to technical.

        Technical/production transitions live in their own level modules
        (technical_check_design_configurator / mrp_technical_configurator).
        """
        self.filtered(lambda lot: lot.design_state == "draft").write(
            {"design_state": "sales_confirmed"}
        )
        return True

    # -- Helpers -------------------------------------------------------------

    @api.model
    def generate_design_lot_name(
        self, product_id, design_params=None, definition_id=False
    ):
        """
        Called from DesignConfiguratorWidget._saveDesignLot() via ORM.
        Returns a unique lot name, taken from the first source that answers:

        1. the sequence of THIS COMBINATION, when the product carries a
           prefix template — every new combination gets its own series;
        2. the product category sequence, if ``product_category_lot_sequence``
           is installed;
        3. the product's own sequence — the standard Odoo field, which also
           carries a ready prefix set from the design properties;
        4. a product-based fallback, so the required field is never empty.
        """
        product = self.env["product.product"].browse(product_id)
        # 1. Комбинацията решава, ако продуктът носи ШАБЛОН за префикс.
        name = self._design_lot_name_from_combination(
            {
                "product_id": product_id,
                "design_params": design_params or {},
                "design_param_definition_id": definition_id,
            }
        )
        if name:
            return name
        # 2. Категорийната последователност (soft-check: без твърда
        # зависимост от product_category_lot_sequence).
        sequence = self.env["ir.sequence"]
        if hasattr(product, "_get_lot_sequence"):
            sequence = product._get_lot_sequence()
        # 3. 🚨 Полето на продукта, НЕ `next_by_code("stock.lot.serial")`:
        # ядрото създава по един запис с този код за всеки нов префикс, така
        # че търсенето само по код ставаше по-непредсказуемо с всеки префикс.
        if not sequence:
            sequence = product.lot_sequence_id
        name = sequence.next_by_id() if sequence else False
        if not name:
            name = (
                f"DL-{product.default_code or product.id}"
                f"-{fields.Datetime.now().strftime('%y%m%d%H%M')}"
            )
        return name

    def action_open_design_configurator(self):
        """
        Button action on stock.lot form view.
        Returns a client action that opens DesignConfiguratorDialog via OWL.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "design_configurator_action",
            "params": {
                "productId": self.product_id.id,
                "definitionId": self.design_param_definition_id.id,
                "existingLotId": self.id,
            },
        }
