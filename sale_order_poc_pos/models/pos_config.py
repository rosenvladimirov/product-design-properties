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
from odoo import models
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = "pos.config"

    def l10n_bg_poc_open(self, payload, line_uuid):
        """Ред на едро в касата → конфигурацията му (POC) за редактора.

        Конфигурацията е на реда на офертата, затова офертата първо се
        запазва (ADR pos-b2b-wholesale/0004: „запазва се сама“). Ред без
        шаблон за конфигурация не се отваря.
        """
        self.ensure_one()
        quotation = self.l10n_bg_b2b_save_quotation(payload)
        line_info = quotation["lines"].get(line_uuid)
        if not line_info:
            raise UserError(self.env._("The line is not in the quotation."))
        so_line = self.env["sale.order.line"].browse(line_info["id"])
        if not so_line.poc_id and not so_line.poc_template_id:
            raise UserError(self.env._(
                "Product %(product)s has no production configuration template.",
                product=so_line.product_id.display_name,
            ))
        poc = so_line.poc_id or self.env["sale.order.poc"].create({"sale_line_id": so_line.id})
        # запазването трие редовете, които касата не носи — допълнителните
        # редове на конфигурацията (сито, дръжки) се връщат, преди касата
        # да ги получи
        if hasattr(poc, "_poc_sync_companion_lines"):
            poc._poc_sync_companion_lines()
        return {"quotation": quotation, "poc": poc._l10n_bg_pos_data()}

    def l10n_bg_poc_save(self, poc_id, updates):
        """Записва параметрите от редактора и пресмята (Compute)."""
        self.ensure_one()
        poc = self.env["sale.order.poc"].browse(poc_id).exists()
        if not poc or poc.company_id != self.company_id:
            raise UserError(self.env._("The configuration does not exist."))
        poc._l10n_bg_pos_write(updates or {})
        poc.action_compute()
        return poc._l10n_bg_pos_data()

    def l10n_bg_poc_report(self, poc_id, key):
        """Справка на конфигурацията, смятана при поискване (бавна е)."""
        self.ensure_one()
        poc = self.env["sale.order.poc"].browse(poc_id).exists()
        if not poc or poc.company_id != self.company_id:
            raise UserError(self.env._("The configuration does not exist."))
        if key not in {report["key"] for report in poc._l10n_bg_pos_reports()}:
            raise UserError(self.env._("Unknown report."))
        return poc._l10n_bg_pos_report(key)

    def _l10n_bg_b2b_quotation_line(self, line, so_line=None):
        # Ред с конфигурация: цената идва от конфигурацията (Compute), не
        # от касата — касата я взема обратно след пресмятането.
        vals = super()._l10n_bg_b2b_quotation_line(line, so_line)
        if so_line and so_line.poc_id:
            vals.pop("price_unit", None)
        return vals
