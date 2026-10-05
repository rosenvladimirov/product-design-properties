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
"""POC е за офертата — конфигураторът не се отваря сам.

Огледалната продажба във фирмата производител няма POC: той е във
фирмата продавач и стига дотук само с дизайн партидата, която е осиновил
(ADR sale-order-poc/0021). Такъв ред е конфигуриран — пазачът преди
процюърмънта не бива да го спира (Солид, 03.10.2026: покупката към
Продакшън не се потвърждаваше, щом вратата носеше шаблон за POC).

При избор на продукт с дизайн дефиниция кубчето се отваря само. Артикул с
шаблон за POC се води през POC на офертата, а до матрицата стига с
поръчката — затова тук конфигураторът не изскача.

Една бройка — един ред (``poc_one_unit_per_line``, Солид 05.10.2026, т. 15):
количество над едно разделя реда на редове по една бройка. Новите носят
копие на конфигурацията, което после се мени поотделно. В потвърдена
поръчка новият ред получава следващата дизайн партида и свой ред в
покупката или производството.
"""

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def get_design_definition_for_product(self, product_id):
        result = super().get_design_definition_for_product(product_id)
        product = self.env["product.product"].browse(product_id).exists()
        if result and product.product_tmpl_id.poc_template_id:
            result = {**result, "autoOpen": False}
        return result

    def _poc_is_configured(self):
        return super()._poc_is_configured() or bool(
            self.sudo().design_lot_id.poc_id
        )

    # -- Една бройка — един ред -------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("poc_no_split"):
            for line in lines:
                extra = line._poc_extra_units(line.product_uom_qty)
                if extra:
                    line.with_context(poc_no_split=True).product_uom_qty = 1.0
                    line._poc_split_units(extra)
        return lines

    def write(self, vals):
        if "product_uom_qty" not in vals or self.env.context.get("poc_no_split"):
            return super().write(vals)
        qty = vals["product_uom_qty"]
        split = self.filtered(lambda line: line._poc_extra_units(qty))
        res = super(SaleOrderLine, self - split).write(vals)
        if split:
            # редът остава с една бройка: в потвърдена поръчка количеството
            # не расте, значи процюърмънтът не добавя втора врата към
            # партидата на първата
            super(SaleOrderLine, split).write(dict(vals, product_uom_qty=1.0))
            for line in split:
                line._poc_split_units(line._poc_extra_units(qty))
        return res

    def _poc_splits_per_unit(self):
        """Редът се разделя ли по бройки.

        Не и огледалният ред във фирмата производител: той носи чужда
        конфигурация през партидата и количеството му идва от покупката.
        """
        self.ensure_one()
        if self.display_type or not self.product_id.poc_one_unit_per_line:
            return False
        lot = self.sudo().design_lot_id
        return not (lot.poc_id and not self.poc_id)

    def _poc_extra_units(self, qty):
        """Колко нови реда иска количеството ``qty`` (0 — нито един)."""
        self.ensure_one()
        if not self._poc_splits_per_unit():
            return 0
        rounding = self.product_uom_id.rounding or 0.01
        if float_compare(qty, 1.0, precision_rounding=rounding) <= 0:
            return 0
        if not float_is_zero(qty - round(qty), precision_rounding=rounding):
            raise UserError(
                self.env._(
                    "%(product)s is sold one unit per line: enter a whole "
                    "number of units.",
                    product=self.product_id.display_name,
                )
            )
        return int(round(qty)) - 1

    def _poc_split_units(self, extra):
        """``extra`` нови реда по една бройка, с копие на конфигурацията.

        В потвърдена поръчка новият ред получава дизайн партида (следващата
        в поредицата) и чак тогава процюърмънт: конфигурацията се осиновява
        в партидата преди него, както при потвърждаването на поръчката.
        """
        self.ensure_one()
        Line = self.with_context(poc_no_split=True)
        vals = Line.copy_data({"order_id": self.order_id.id, "product_uom_qty": 1.0})[0]
        confirmed = self.state == "sale"
        news = self.env["sale.order.line"]
        for _unit in range(extra):
            # без конфигурация процюърмънтът на нов ред в потвърдена поръчка
            # чака (sale_order_poc, poc_defer_launch) — тук той тръгва по-долу
            new = Line.create(dict(vals))
            if self.poc_id:
                self.poc_id.sudo().copy(
                    {
                        "sale_line_id": new.id,
                        "sale_description_block": self.poc_id.sale_description_block,
                    }
                )
            news |= new
        if confirmed:
            news._design_lot_on_confirm()
            news.with_context(poc_no_split=True)._action_launch_stock_rule()
        return news
