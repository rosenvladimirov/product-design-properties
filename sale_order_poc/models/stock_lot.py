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
from odoo import fields, models


class StockLot(models.Model):
    """Лотът принадлежи на конфигурацията (ADR sale-order-poc/0007).

    Един POC → много лотове, един лот → най-много един POC. Лотовете на
    POC за един продукт са семейство, подредено по ``poc_batch``.
    Идентичността е връзка, не име.
    """

    _inherit = "stock.lot"

    poc_id = fields.Many2one(
        "sale.order.poc",
        string="Production Configuration",
        index="btree_not_null",
        ondelete="restrict",
        readonly=True,
        copy=False,
    )
    poc_batch = fields.Integer(string="Batch", readonly=True, copy=False)
    # схемата иска път с точно една точка (ORM/fields_properties.py:96)
    poc_template_id = fields.Many2one(related="poc_id.template_id", store=True)
    poc_params = fields.Properties(
        string="Configuration",
        related="poc_id.params",
        definition="poc_template_id.param_definition",
        readonly=True,
    )
    poc_summary = fields.Char(related="poc_id.summary")

    _poc_batch_uniq = models.Constraint(
        "unique(poc_id, product_id, poc_batch)",
        "A batch number appears once per configuration and product.",
    )
