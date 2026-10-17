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
import datetime

from odoo import api, fields, models
from odoo.tools.image import image_data_uri

from .sale_order_poc_drawing import SIMPLE_TYPES


def _present(value):
    """Има ли стойност за рисунката: None, празен низ, празен запис или
    списък нямат; 0 и False имат."""
    if value is None or value == "":
        return False
    if isinstance(value, (models.BaseModel, list, tuple)) and not value:
        return False
    return True


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    drawing_svg = fields.Html(
        string="Drawing", compute="_compute_drawing", sanitize=False
    )
    drawing_url = fields.Char(string="Drawing Picture URL", compute="_compute_drawing")

    @api.depends(
        "params",
        "aspect_ids.params",
        "template_id.drawing_picture",
        "template_id.drawing_template_id.svg",
        "template_id.drawing_defaults",
        "template_id.drawing_caption",
    )
    def _compute_drawing(self):
        for poc in self:
            poc.drawing_svg = False
            poc.drawing_url = False
            if not poc.template_id:
                continue
            if poc.template_id.sudo().drawing_picture:
                # във формата — по адрес, не base64 в HTML-а
                poc.drawing_url = "/web/image/sale.order.poc.template/%d/drawing_picture" % (
                    poc.template_id.id
                )
                continue
            drawing = poc._poc_drawing() or {}
            poc.drawing_svg = drawing.get("svg") or False
            poc.drawing_url = drawing.get("url") or False

    # ── Рисунката (SPEC sale-order-poc/drawing § 3.3) ───────────────

    def _poc_drawing(self, values=None):
        """Рисунката на изделието: ``{"url"}`` или ``{"svg", "caption"}`` или False.

        Редът на предимство: качената картинка на шаблона → SVG шаблонът от
        библиотеката (подразбиране < записаните стойности < ``values``) →
        куката на вертикала `_poc_drawing_fallback` → нищо. ``values`` са
        незаписаните стойности (касата). НИКОГА не пише.
        """
        self.ensure_one()
        template = self.template_id.sudo()
        if not template:
            return False
        if template.drawing_picture:
            return {"url": image_data_uri(template.drawing_picture)}
        if template.drawing_template_id:
            merged = self._poc_drawing_merged(values)
            svg = template.drawing_template_id._render_svg(self._poc_drawing_values(merged))
            if svg:
                result = {"svg": svg}
                caption = self._poc_render(template.drawing_caption, extra=merged)
                if caption:
                    result["caption"] = caption
                return result
        return self._poc_drawing_fallback(values) or False

    def _poc_drawing_fallback(self, values=None):
        """Кука за вертикала, когато шаблонът няма рисунка (Пакит: разгъвката)."""
        return False

    def _poc_drawing_merged(self, values=None):
        """Стойностите за рисунката в суровия вид на `_poc_values()`.

        Подразбирането на шаблона, отгоре записаните стойности, отгоре
        незаписаните ``values``. Празното не закрива подразбирането.
        """
        self.ensure_one()
        defaults = self.template_id.sudo()._poc_drawing_default_values()
        merged = dict(defaults)
        merged.update(self._poc_drawing_present(self._poc_values()))
        for code, value in (values or {}).items():
            if _present(value):
                merged[code] = value
            elif code in defaults:
                # изчистеното в касата поле — пак подразбирането
                merged[code] = defaults[code]
            else:
                merged.pop(code, None)
        return merged

    @api.model
    def _poc_drawing_present(self, values):
        return {code: value for code, value in values.items() if _present(value)}

    def _poc_drawing_values(self, merged):
        """`v` на шаблона: САМО прости стойности, никога записи.

        Числата, низовете и ключовете на селекциите минават; many2one/many2many
        стават имена (display_name); датата — ISO низ; таговете — ключове през
        запетая; таблиците изпадат. Цветът на избраната опция или продукт е
        ``v["<код>__color"]``.
        """
        self.ensure_one()
        params = {param.code: param for param in self._poc_params()}
        v = {}
        for code, value in merged.items():
            if isinstance(value, models.BaseModel):
                v[code] = ", ".join(value.mapped("display_name")) if value else None
                record = value[:1]
                color = record["drawing_color"] if "drawing_color" in record._fields else False
                if color:
                    v["%s__color" % code] = color
            elif isinstance(value, datetime.date):
                v[code] = value.isoformat()
            elif isinstance(value, (list, tuple)):
                if all(isinstance(item, str) for item in value):
                    v[code] = ",".join(value)
            elif isinstance(value, SIMPLE_TYPES):
                v[code] = value
                param = params.get(code)
                if param and param.param_type == "selection" and isinstance(value, str):
                    option = param.option_ids.filtered(lambda o, key=value: o.key == key)[:1]
                    if option.drawing_color:
                        v["%s__color" % code] = option.drawing_color
        return v
