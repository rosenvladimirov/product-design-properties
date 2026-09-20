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
from odoo.exceptions import ValidationError


class SaleOrderPocLine(models.Model):
    """Ред на параметър тип таблица: рецепта по секции, цветове с норми,
    опаковъчни роли (ADR sale-order-poc/0004).

    Във формулата таблицата е списък от редове по sequence; празната клетка
    е ЛИПСВАЩ ред, не нула. До производството стига през ``add_products``
    на формулата (ADR sale-order-poc/0012).
    """

    _name = "sale.order.poc.line"
    _description = "Production Configuration Table Row"
    _order = "param_id, sequence, id"

    poc_id = fields.Many2one(
        "sale.order.poc", required=True, ondelete="cascade", index=True
    )
    param_id = fields.Many2one(
        "sale.order.poc.param",
        string="Table",
        required=True,
        ondelete="restrict",
        domain="[('param_type', '=', 'table')]",
    )
    sequence = fields.Integer(default=10)
    key = fields.Char(help="The axis of the row: a section, a colour, a role.")
    product_id = fields.Many2one("product.product", string="Product")
    value = fields.Float()
    uom_id = fields.Many2one("uom.uom", string="Unit")

    @api.constrains("param_id")
    def _check_param(self):
        for line in self:
            if line.param_id.param_type != "table":
                raise ValidationError(
                    self.env._(
                        "%(param)s is not a table parameter.",
                        param=line.param_id.display_name,
                    )
                )
            if line.param_id not in line.poc_id._poc_table_params():
                raise ValidationError(
                    self.env._(
                        "Table %(param)s is not in the template of %(poc)s or in "
                        "its aspects.",
                        param=line.param_id.display_name,
                        poc=line.poc_id.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.poc_id._poc_check_children_editable()
        lines.poc_id._poc_compute_derived()
        return lines

    def write(self, vals):
        if self.env.context.get("poc_system"):
            return super().write(vals)
        self.poc_id._poc_check_children_editable()
        res = super().write(vals)
        self.poc_id._poc_compute_derived()
        return res

    def unlink(self):
        pocs = self.poc_id
        pocs._poc_check_children_editable()
        res = super().unlink()
        pocs._poc_compute_derived()
        return res
