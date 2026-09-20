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


class SaleOrderPocAspect(models.Model):
    """Аспект на конфигурацията: шаблон, добавен към конкретен POC.

    Печатът, етикетът или опаковъчната схема не са на всеки продукт, затова
    не са в основния шаблон. Всеки аспект е свой контейнер, защото Properties
    има точно един контейнер на запис (ORM/fields_properties.py:401-405);
    кодовете му не застъпват основния шаблон, така че за формулите
    пространството е едно (ADR sale-order-poc/0004).
    """

    _name = "sale.order.poc.aspect"
    _description = "Production Configuration Aspect"
    _order = "sequence, id"

    poc_id = fields.Many2one(
        "sale.order.poc", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    allowed_aspect_ids = fields.Many2many(
        related="poc_id.template_id.allowed_aspect_ids"
    )
    template_id = fields.Many2one(
        "sale.order.poc.template",
        string="Aspect",
        required=True,
        ondelete="restrict",
        domain="[('id', 'in', allowed_aspect_ids)]",
    )
    params = fields.Properties(
        string="Parameters",
        definition="template_id.param_definition",
        copy=True,
    )
    param_origins = fields.Json(copy=True, readonly=True)

    _aspect_uniq = models.Constraint(
        "unique(poc_id, template_id)", "An aspect appears once per configuration."
    )

    @api.depends("template_id")
    def _compute_display_name(self):
        for aspect in self:
            aspect.display_name = aspect.template_id.display_name

    @api.constrains("template_id")
    def _check_template(self):
        for aspect in self:
            template = aspect.template_id
            if template.usage != "aspect":
                raise ValidationError(
                    self.env._(
                        "%(template)s is not an aspect.", template=template.display_name
                    )
                )
            allowed = aspect.poc_id.template_id.allowed_aspect_ids
            if template not in allowed:
                raise ValidationError(
                    self.env._(
                        "%(aspect)s is not allowed by template %(template)s.",
                        aspect=template.display_name,
                        template=aspect.poc_id.template_id.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        aspects = super().create(vals_list)
        pocs = aspects.poc_id
        pocs._poc_check_children_editable()
        for aspect in aspects:
            aspect.poc_id._poc_apply_defaults()
        pocs._poc_compute_derived()
        return aspects

    def write(self, vals):
        if self.env.context.get("poc_system"):
            return super().write(vals)
        self.poc_id._poc_check_children_editable()
        before = {poc.id: poc._poc_values() for poc in self.poc_id}
        res = super().write(vals)
        for poc in self.poc_id:
            if "params" in vals:
                poc._poc_mark_manual(before[poc.id])
            poc._poc_compute_derived()
            poc._poc_post_changes(before[poc.id])
        return res

    def unlink(self):
        pocs = self.poc_id
        pocs._poc_check_children_editable()
        res = super().unlink()
        pocs._poc_compute_derived()
        return res
