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
import json
import logging
import re

from lxml import etree
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..drawing_helpers import make_helpers

_logger = logging.getLogger(__name__)

# простите типове, които шаблонът вижда в `v` (SPEC § 3.2)
SIMPLE_TYPES = (bool, int, float, str, type(None))
CODES_SPLIT_RE = re.compile(r"[\s,;]+")


def simple_values(values):
    """Само простите стойности: всичко друго изпада (записи, списъци…)."""
    return {
        str(key): value
        for key, value in (values or {}).items()
        if isinstance(value, SIMPLE_TYPES)
    }


class SaleOrderPocDrawing(models.Model):
    """Библиотеката на SVG шаблоните на рисунката (ADR sale-order-poc/0025).

    Шаблонът е QWeb (Odoo 19), записан в базата — т.е. код. Пише го само
    група „Drawing Designer“ (Росен, 17.10.2026, О1), а в контекста му има
    само прости стойности (`v`) и чисти помощници (`d`), никога записи.
    """

    _name = "sale.order.poc.drawing"
    _description = "Production Configuration Drawing"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    svg = fields.Text(
        string="SVG Template",
        help="QWeb template of the drawing. It sees only `v` (the values of the "
        "parameters by code: numbers, texts, selection keys, record names and "
        "`v['<code>__color']`) and `d` (pure drawing helpers: iso, pts, box, face, "
        "flap, rect, line, dim_line, viewbox, stroke_width, shade, color, num). "
        "It must return a whole <svg> element.",
    )
    parameter_codes = fields.Char(
        string="Expected Parameters",
        help="Codes of the parameters the drawing reads, separated by commas. "
        "For documentation and checks only.",
    )
    sample_values = fields.Json(
        string="Sample Values (JSON)",
        help="Values the preview is drawn with, by parameter code.",
    )
    sample_values_text = fields.Text(
        string="Sample Values",
        compute="_compute_sample_values_text",
        inverse="_inverse_sample_values_text",
        help='Values the preview is drawn with, as JSON, e.g. {"width": 900, "height": 2000}.',
    )
    preview = fields.Html(compute="_compute_preview", sanitize=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company", index=True)

    _code_uniq = models.Constraint(
        "unique(code)", "The code of the drawing must be unique."
    )

    @api.depends("sample_values")
    def _compute_sample_values_text(self):
        for drawing in self:
            drawing.sample_values_text = (
                json.dumps(drawing.sample_values, ensure_ascii=False, indent=2)
                if drawing.sample_values
                else ""
            )

    def _inverse_sample_values_text(self):
        for drawing in self:
            text = (drawing.sample_values_text or "").strip()
            if not text:
                drawing.sample_values = False
                continue
            try:
                parsed = json.loads(text)
            except ValueError as error:
                raise ValidationError(
                    self.env._("The sample values are not valid JSON: %(error)s", error=error)
                ) from error
            if not isinstance(parsed, dict):
                raise ValidationError(
                    self.env._("The sample values must be a JSON object: {\"code\": value}.")
                )
            drawing.sample_values = parsed

    @api.depends("svg", "sample_values")
    def _compute_preview(self):
        for drawing in self:
            drawing.preview = drawing._render_svg(drawing.sample_values or {}) or False

    def _parameter_code_list(self):
        """Очакваните кодове като списък."""
        self.ensure_one()
        return [code for code in CODES_SPLIT_RE.split(self.parameter_codes or "") if code]

    def _render_svg(self, values):
        """SVG-то по стойностите — празно при грешка, никога изключение.

        ``values`` се свеждат до прости типове (записите изпадат), а
        помощниците са чисти функции: шаблонът няма път до env.
        """
        self.ensure_one()
        if not self.svg:
            return ""
        try:
            return self._render_svg_raw(values)
        except Exception as error:  # noqa: BLE001 — рисунката не сваля формата и касата
            _logger.warning(
                "The drawing %s cannot be rendered: %s", self.code, error
            )
            return ""

    def _render_svg_raw(self, values):
        """QWeb от низ с минимален контекст: само ``v`` и ``d``."""
        v = simple_values(values)
        root = etree.fromstring(self.svg.strip())
        rendered = self.env["ir.qweb"]._render(
            root, {"v": v, "d": make_helpers(v)}, minimal_qcontext=True
        )
        return Markup(str(rendered).strip())
