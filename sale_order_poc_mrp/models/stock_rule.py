# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
from odoo import Command, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _make_mo_get_domain(self, procurement, bom):
        # един основен BoM за всички поръчки (ADR sale-order-poc/0008): без
        # POC в домейна редовете на различни конфигурации се сливат в едно MO
        return super()._make_mo_get_domain(procurement, bom) + (
            ("poc_id", "=", procurement.values.get("poc_id") or False),
        )

    def _prepare_mo_vals(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
        bom,
    ):
        vals = super()._prepare_mo_vals(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
            bom,
        )
        poc = self.env["sale.order.poc"].sudo().browse(values.get("poc_id") or [])
        if not poc:
            return vals
        vals["poc_id"] = poc.id
        if product_id.tracking == "lot":
            # за крайния продукт това е лотът на POC; за полуфабриката — лотът
            # на компонента, роден тук, където е сигурно, че се произвежда
            vals["lot_producing_ids"] = [Command.set(poc._poc_lot(product_id).ids)]
        if poc.summary:
            description = vals.get("product_description_variants") or ""
            vals["product_description_variants"] = " · ".join(
                filter(None, [description, poc.summary])
            )
        if product_id != poc.product_id and poc.template_id.restrict_component_lots:
            self._poc_restrict_dest_chain(values.get("move_dest_ids"), poc)
        return vals

    def _poc_restrict_dest_chain(self, moves, poc):
        """Суровината, произведена за POC, се резервира само от семейството.

        Веригата от движения до суровинното на родителското MO — едно при
        производство в една стъпка, две при pbm (подаването към
        производството и самата суровина).
        """
        seen = self.env["stock.move"]
        while moves:
            moves = moves.filtered(lambda m: m.poc_id == poc) - seen
            seen |= moves
            moves.sudo().poc_lot_restrict = True
            moves = moves.filtered(lambda m: not m.raw_material_production_id)
            moves = moves.move_dest_ids
