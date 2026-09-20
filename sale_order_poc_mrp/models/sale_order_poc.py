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


class SaleOrderPocTemplate(models.Model):
    _inherit = "sale.order.poc.template"

    # флаговете от ADR sale-order-poc/0007, дошли с бекордерите (ADR 0013)
    lot_batches = fields.Boolean(
        string="New Lot per Backorder",
        help="Each backorder of a manufacturing order gets the next batch of "
        "the configuration lot. The delivery takes all batches.",
    )
    restrict_component_lots = fields.Boolean(
        string="Reserve Own Component Lots",
        default=True,
        help="A component manufactured for the configuration is reserved only "
        "from the configuration's own lots. Off: the operator picks any lot.",
    )


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    production_ids = fields.One2many("mrp.production", "poc_id", string="Manufacturing")
    production_count = fields.Integer(compute="_compute_production_count")

    def _compute_production_count(self):
        for poc in self:
            poc.production_count = len(poc.production_ids)

    def _poc_compute_derived(self):
        res = super()._poc_compute_derived()
        # всяка промяна на параметрите стига до производството (ADR
        # sale-order-poc/0008): чернови и незапочнати — автоматично,
        # започнатите — activity и бутон. През sudo(): редакторът на POC може
        # да е мениджър продажби без права в производството (ADR 0010)
        self.sudo().production_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        )._poc_refresh()
        return res

    def action_view_productions(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "mrp.mrp_production_action"
        )
        action["domain"] = [("poc_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
