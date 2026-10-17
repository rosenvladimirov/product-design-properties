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
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError

DRAWING_GROUP = "sale_order_poc_drawing.group_drawing_designer"
# полетата на рисунката в шаблона — пише ги само Drawing Designer (О1)
DRAWING_FIELDS = frozenset(
    {"drawing_picture", "drawing_template_id", "drawing_defaults", "drawing_caption"}
)
DEFAULT_SPLIT_RE = re.compile(r"[,;\n]+")


def parse_defaults(text):
    """``код=стойност`` (разделени със запетая или нов ред) → речник.

    Числото става float, ``true``/``false`` — bool, другото остава низ
    (например ключ на селекция). Редове без ``=`` изпадат.
    """
    values = {}
    for part in DEFAULT_SPLIT_RE.split(text or ""):
        if "=" not in part:
            continue
        code, raw = (piece.strip() for piece in part.split("=", 1))
        if not code:
            continue
        lowered = raw.lower()
        if lowered in ("true", "false"):
            values[code] = lowered == "true"
            continue
        try:
            values[code] = float(raw)
        except ValueError:
            values[code] = raw
    return values


class SaleOrderPocTemplate(models.Model):
    _inherit = "sale.order.poc.template"

    drawing_picture = fields.Image(
        string="Drawing Picture",
        max_width=1024,
        max_height=1024,
        help="Uploaded picture of the product. It always wins over the SVG template.",
    )
    drawing_template_id = fields.Many2one(
        "sale.order.poc.drawing",
        string="Drawing Template",
        ondelete="restrict",
        help="SVG template from the drawing library, drawn with the values of the "
        "configuration.",
    )
    drawing_defaults = fields.Text(
        string="Drawing Defaults",
        help="Values for an empty configuration, as code=value separated by commas "
        "or new lines, e.g. box_l=300, box_w=200, box_d=150.",
    )
    drawing_caption = fields.Char(
        string="Drawing Caption",
        translate=True,
        help="Caption under the drawing, with {{ code }} placeholders, "
        "e.g. {{ box_l }} × {{ box_w }} × {{ box_d }} mm.",
    )
    drawing_preview = fields.Html(
        string="Drawing Preview", compute="_compute_drawing_preview", sanitize=False
    )
    drawing_missing_codes = fields.Char(
        string="Codes Not in the Template",
        compute="_compute_drawing_preview",
        help="Codes the drawing expects that neither the parameters of the template "
        "nor the drawing defaults provide.",
    )
    drawing_can_edit = fields.Boolean(
        string="Can Edit the Drawing", compute="_compute_drawing_can_edit"
    )

    @api.depends_context("uid")
    def _compute_drawing_can_edit(self):
        allowed = self.env.su or self.env.user.has_group(DRAWING_GROUP)
        for template in self:
            template.drawing_can_edit = allowed

    @api.depends(
        "drawing_template_id.svg",
        "drawing_template_id.sample_values",
        "drawing_template_id.parameter_codes",
        "drawing_defaults",
        "line_ids.param_id",
    )
    def _compute_drawing_preview(self):
        for template in self:
            drawing = template.sudo().drawing_template_id
            if not drawing:
                template.drawing_preview = False
                template.drawing_missing_codes = False
                continue
            values = {
                **(drawing.sample_values or {}),
                **template._poc_drawing_default_values(),
            }
            template.drawing_preview = drawing._render_svg(values) or False
            known = set(template.line_ids.param_id.mapped("code")) | set(
                template._poc_drawing_default_values()
            )
            missing = [code for code in drawing._parameter_code_list() if code not in known]
            template.drawing_missing_codes = ", ".join(missing) or False

    def _poc_drawing_default_values(self):
        """Подразбирането на рисунката като речник (прости стойности)."""
        self.ensure_one()
        return parse_defaults(self.drawing_defaults)

    # ── Кой пише рисунката (О1) ─────────────────────────────────────

    def _poc_drawing_check_access(self, vals):
        if self.env.su or self.env.context.get("poc_drawing_copy"):
            return
        if DRAWING_FIELDS & set(vals) and not self.env.user.has_group(DRAWING_GROUP):
            raise AccessError(
                self.env._(
                    "Only a Drawing Designer can change the drawing of a "
                    "configuration template."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # празните стойности не са промяна на рисунката
            self._poc_drawing_check_access(
                {key: value for key, value in vals.items() if value}
            )
        return super().create(vals_list)

    def write(self, vals):
        self._poc_drawing_check_access(vals)
        return super().write(vals)

    def copy(self, default=None):
        # копието носи вече одобрената рисунка — не е нов код
        copies = super(
            SaleOrderPocTemplate, self.with_context(poc_drawing_copy=True)
        ).copy(default=default)
        # знакът за копието не остава в средата на върнатите записи
        return copies.with_env(self.env)
