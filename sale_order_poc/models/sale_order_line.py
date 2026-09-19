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
from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    poc_ids = fields.One2many("sale.order.poc", "sale_line_id")
    poc_id = fields.Many2one(
        "sale.order.poc",
        string="Production Configuration",
        compute="_compute_poc_id",
        store=True,
        index="btree_not_null",
    )
    poc_template_id = fields.Many2one(
        related="product_id.product_tmpl_id.poc_template_id"
    )
    poc_summary = fields.Char(related="poc_id.summary", string="Configuration")
    poc_lot_id = fields.Many2one(related="poc_id.lot_id", string="Configuration Lot")

    @api.depends("poc_ids")
    def _compute_poc_id(self):
        for line in self:
            line.poc_id = line.poc_ids[:1]

    @api.model_create_multi
    def create(self, vals_list):
        # Ред, добавен към потвърдена поръчка, пуска процюърмънт още при
        # create (CORE sale_stock/models/sale_order_line.py:249-252), когато
        # конфигурация още няма: редът чака „Release to Production“.
        lines = super(SaleOrderLine, self.with_context(poc_defer_launch=True)).create(
            vals_list
        )
        return lines.with_env(self.env)

    def action_open_poc(self):
        self.ensure_one()
        if not self.poc_id and not self.poc_template_id:
            raise UserError(
                self.env._(
                    "Product %(product)s has no production configuration template.",
                    product=self.product_id.display_name,
                )
            )
        poc = self.poc_id or self.env["sale.order.poc"].create(
            {"sale_line_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order.poc",
            "res_id": poc.id,
            "view_mode": "form",
            "target": "current",
        }

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        if self.poc_id:
            # пътуват по движенията като sale_line_id (stock.rule
            # _get_custom_move_fields) — ADR sale-order-poc/0007
            values["poc_id"] = self.poc_id.id
            values["poc_lot_restrict"] = self.product_id.tracking != "none"
        return values

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        """Пазачът и Stage 1 — точно преди процюърмънта.

        Оттук минават и трите пътя: потвърждаване на поръчката, промяна на
        количеството на потвърден ред и нов ред в потвърдена поръчка (CORE
        sale_stock/models/sale_order_line.py:385). Количеството вече е
        записано, а процюърмънтът още не е тръгнал.
        """
        if self.env.context.get("skip_procurement"):
            return super()._action_launch_stock_rule(
                previous_product_uom_qty=previous_product_uom_qty
            )
        lines = self.filtered(
            lambda line: line.state == "sale"
            and (line.poc_id or line.poc_template_id)
        )
        missing = lines.filtered(lambda line: not line.poc_id)
        if missing and self.env.context.get("poc_defer_launch"):
            self -= missing
            lines -= missing
        elif missing:
            raise UserError(
                self.env._(
                    "Configure production before confirming: %(products)s",
                    products=", ".join(missing.mapped("product_id.display_name")),
                )
            )
        lines.poc_id._poc_confirm()
        return super()._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty
        )
