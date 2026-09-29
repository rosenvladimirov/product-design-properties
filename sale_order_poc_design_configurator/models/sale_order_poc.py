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
"""Една поръчка — една партида (ADR sale-order-poc/0019).

Конфигураторът на дизайна ражда партида на реда на продажбата и тя пътува до
производствената поръчка. POC също ражда партида. Без този мост една поръчка
получава ДВЕ партиди, тоест две истини: коя носи параметрите на изделието и
коя — конфигурацията.

Тук POC осиновява вече съществуващата: записва се върху нея, вместо да
създава своя. Ред без дизайн минава по стандартния път на POC. След
потвърждаване партидата на POC е и дизайн партидата на реда — фиксирана:
оттам нататък матрицата чете от нея, не от POC.
"""

import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    def _poc_ensure_lot(self):
        """Осиновява партидата на дизайна; после я фиксира на реда."""
        for poc in self:
            lot = poc._poc_design_lot()
            if lot:
                poc._poc_adopt_lot(lot)
        # осиновената вече е в lot_id: основата не ражда втора, а матрицата
        # пише параметрите си и в нея
        res = super()._poc_ensure_lot()
        for poc in self:
            if poc.lot_id:
                poc._poc_fix_design_lot(poc.lot_id)
        return res

    def _poc_design_lot(self):
        """Партидата на дизайна за този ред — или празно.

        Празно значи „няма какво да се осиновява“: ред без конфигуратор,
        POC с вече своя партида, или партида на друг продукт (тогава двете
        не описват едно и също нещо и сливането им би било грешка).
        """
        self.ensure_one()
        Lot = self.env["stock.lot"]
        if self.lot_id:
            return Lot
        lot = self.sale_line_id.design_lot_id
        if not lot:
            return Lot
        if self.product_id and lot.product_id != self.product_id:
            _logger.warning(
                "POC %s: design lot %s is for %s, not for %s — not adopted.",
                self.name,
                lot.name,
                lot.product_id.display_name,
                self.product_id.display_name,
            )
            return Lot
        return lot

    def _poc_adopt_lot(self, lot):
        """Записва конфигурацията върху партидата на дизайна.

        Партида, която вече принадлежи на ДРУГА конфигурация, спира с
        грешка: тихото преподписване би пренаредило семейството
        ``(poc_id, product_id)`` и резервациите по него.
        """
        self.ensure_one()
        if lot.poc_id and lot.poc_id != self:
            raise UserError(
                self.env._(
                    "Lot %(lot)s already belongs to configuration %(other)s — "
                    "it cannot be adopted by %(poc)s.",
                    lot=lot.name,
                    other=lot.poc_id.name,
                    poc=self.name,
                )
            )
        vals = {"poc_id": self.id, "poc_batch": lot.poc_batch or 1}
        if not lot.ref:
            vals["ref"] = self.name
        lot.sudo().write(vals)
        self.lot_id = lot.id
        _logger.info("POC %s adopted design lot %s.", self.name, lot.name)
        return lot

    def _poc_fix_design_lot(self, lot):
        """Партидата на POC става дизайн партида на реда — фиксирана.

        Без това кубчето на потвърдената поръчка се отваряше БЕЗ партида и
        при запис раждаше втора. Оттук нататък матрицата чете от партидата,
        не от POC. Върви преди процюърмънта, затова и производствената
        поръчка получава същата партида.
        """
        self.ensure_one()
        line = self.sudo().sale_line_id
        if not line.design_lot_id:
            line.design_lot_id = lot
        if lot.design_state == "draft":
            # системен преход, както партидата на POC: продавач без складови
            # права потвърждава поръчката. Иначе конфигураторът го прави при
            # потвърждаване с правата на продавача и пада на записа в партидата.
            lot.sudo().design_state = "sales_confirmed"
