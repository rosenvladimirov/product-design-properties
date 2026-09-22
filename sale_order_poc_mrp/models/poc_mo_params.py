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
"""Кои параметри на POC се виждат във формата на MO (ADR sale-order-poc/0018).

Отметката е на реда на шаблона: един параметър може да е за цеха в един
шаблон и само за търговеца в друг. Речникът дава подразбирането, както
``show_in_workorder`` на модула за цеха.
"""

from odoo import api, fields, models


class SaleOrderPocParam(models.Model):
    _inherit = "sale.order.poc.param"

    show_in_production = fields.Boolean(
        string="Show in Manufacturing Order",
        help="Default for the template lines that use this parameter: the "
        "value is shown on the manufacturing order form.",
    )


class SaleOrderPocTemplateLine(models.Model):
    _inherit = "sale.order.poc.template.line"

    # речникът дава подразбирането, редът носи действащата стойност
    show_in_production = fields.Boolean(
        string="Show in Manufacturing Order",
        compute="_compute_show_in_production",
        store=True,
        readonly=False,
        help="The value of this parameter is shown on the manufacturing order "
        "form, next to the responsible person.",
    )

    @api.depends("param_id")
    def _compute_show_in_production(self):
        for line in self:
            line.show_in_production = line.param_id.show_in_production


class SaleOrderPocTemplate(models.Model):
    _inherit = "sale.order.poc.template"

    mo_param_definition = fields.PropertiesDefinition(
        string="Manufacturing Order Parameters",
        compute="_compute_mo_param_definition",
        store=True,
        readonly=True,
        help="The part of the schema shown on the manufacturing order: only the "
        "lines marked 'Show in Manufacturing Order'.",
    )

    @api.depends("param_definition", "line_ids.param_id", "line_ids.show_in_production")
    def _compute_mo_param_definition(self):
        for template in self:
            shown = set(
                template.line_ids.filtered("show_in_production").param_id.mapped("code")
            )
            definition = []
            section = None
            for entry in template.param_definition or []:
                if entry.get("type") == "separator":
                    section = entry
                    continue
                if entry.get("name") not in shown:
                    continue
                # разделителят влиза само пред свой показан параметър и никога
                # сгънат: в MO стойностите трябва да се виждат веднага
                if section:
                    definition.append({**section, "fold_by_default": False})
                    section = None
                definition.append(entry)
            template.mo_param_definition = definition or False
