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
"""Стандартният продукт вместо изделие по поръчка (ADR sale-order-poc/0027).

Шаблонът казва кои параметри са размерът; готовите продукти дават своя от
атрибут, маркиран като размер. Най-близките готови са алтернативи; изборът
сменя артикула в реда, а POC остава като история на искането.
"""
import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

SIZE_UNITS = [("mm", "mm"), ("cm", "cm")]
TO_MM = {"mm": 1.0, "cm": 10.0}
_NUMBER = r"(\d+(?:[.,]\d+)?)"
_SEP = r"\s*[x×хX*]\s*"
# „30×20×15“, „10,5×10×3 см“, „40×30×30 см, трипластно C“ — числата отпред,
# опционална единица веднага след тях, останалото е описание
SIZE_RE = re.compile(
    r"^\s*" + _NUMBER + _SEP + _NUMBER + r"(?:" + _SEP + _NUMBER + r")?"
    r"\s*(мм|mm|см|cm)?",
    re.IGNORECASE,
)
UNIT_WORDS = {"мм": "mm", "mm": "mm", "см": "cm", "cm": "cm"}
# половин милиметър: закръгленията в каталога не изхвърлят точния размер
EPSILON_MM = 0.5


def parse_size_mm(text, unit):
    """Размерът в мм от текста на стойност на атрибут — или празен списък."""
    match = SIZE_RE.match(text or "")
    if not match:
        return []
    numbers = [float(n.replace(",", ".")) for n in match.groups()[:3] if n]
    factor = TO_MM[UNIT_WORDS.get((match.group(4) or "").lower(), unit)]
    return [n * factor for n in numbers]


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    poc_size_unit = fields.Selection(
        SIZE_UNITS,
        string="Size Unit",
        help="The values of this attribute are sizes such as 40×30×25, in this "
        "unit unless the value names its own. Production configurations use "
        "them to find standard products close to the requested size.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _poc_size_mm(self):
        """Размерът на варианта в мм (Д, Ш, В) — или празен списък.

        От първата стойност на атрибут с единица за размер. Фирмен слой с
        полета за размер ги дава преди атрибута.
        """
        self.ensure_one()
        for ptav in self.product_template_attribute_value_ids:
            unit = ptav.attribute_id.poc_size_unit
            if unit:
                size = parse_size_mm(ptav.product_attribute_value_id.name, unit)
                if size:
                    return size
        return []

    @api.model
    def _poc_size_domain(self):
        """Кои варианти изобщо имат размер — стесняване преди сравнението."""
        return [("product_template_attribute_value_ids.attribute_id.poc_size_unit", "!=", False)]


class SaleOrderPocTemplate(models.Model):
    _inherit = "sale.order.poc.template"

    alternative_size_codes = fields.Char(
        string="Size Parameters",
        help="Codes of the parameters that give the size in mm, in the order "
        "length, width, height, separated by commas (e.g. box_l, box_w, "
        "box_d). Leave empty to look for no standard products.",
    )
    alternative_tolerance = fields.Float(
        string="Size Tolerance (%)",
        default=20.0,
        help="A standard product is an alternative when each of its sizes is "
        "from the requested one up to this much larger.",
    )
    alternative_domain = fields.Char(
        string="Standard Products",
        default="[('sale_ok', '=', True)]",
        help="Which products may be offered instead of the configured one.",
    )
    alternative_limit = fields.Integer(
        string="Alternatives Shown",
        default=3,
    )

    def _poc_alternative_codes(self):
        self.ensure_one()
        return [
            code.strip()
            for code in (self.alternative_size_codes or "").split(",")
            if code.strip()
        ]


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    standard_product_id = fields.Many2one(
        "product.product",
        string="Standard Product",
        copy=False,
        tracking=True,
        help="A ready product chosen instead of making the configured one. The "
        "order line takes this product and its price; the configuration stays "
        "as the record of the request, without lot, matrix or extra lines.",
    )
    # артикулът на реда преди избора — връщането го възстановява
    configured_product_id = fields.Many2one(
        "product.product", string="Configured Product", readonly=True, copy=False
    )
    alternative_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_alternative_product_ids",
        string="Close Standard Products",
    )
    alternative_enabled = fields.Boolean(compute="_compute_alternative_product_ids")

    @api.depends("params", "template_id")
    def _compute_alternative_product_ids(self):
        for poc in self:
            poc.alternative_enabled = bool(poc.template_id._poc_alternative_codes())
            products = self.env["product.product"]
            for candidate in poc._poc_alternatives():
                products |= candidate["product"]
            poc.alternative_product_ids = products

    def _poc_requested_size(self):
        """Поисканият размер в мм по кодовете на шаблона; None за липсващата."""
        self.ensure_one()
        values = self._poc_values()
        size = []
        for code in self.template_id._poc_alternative_codes():
            value = values.get(code)
            size.append(float(value) if isinstance(value, (int, float)) and value > 0 else None)
        return size

    def _poc_alternatives(self):
        """Най-близките готови продукти: [{product, size, excess}].

        Готовият е алтернатива, когато всяка ЗАДАДЕНА мярка е от поисканата
        до поисканата + допуска; дължина и ширина може да се разменят.
        Липсващата мярка не се сравнява — затова и „неясният“ размер (само
        Д × Ш) намира кандидати. Подредба: сумата на относителните излишъци,
        после цената.
        """
        self.ensure_one()
        template = self.template_id
        if not template._poc_alternative_codes():
            return []
        requested = self._poc_requested_size()
        given = [i for i, value in enumerate(requested) if value]
        if not given:
            return []
        tolerance = max(template.alternative_tolerance or 0.0, 0.0) / 100.0
        Product = self.env["product.product"]
        domain = safe_eval(template.alternative_domain or "[]")
        domain += Product._poc_size_domain()
        # изделията по поръчка не са „готови“
        domain += [("product_tmpl_id.poc_template_id", "=", False)]
        if self.configured_product_id:
            domain += [("id", "!=", self.configured_product_id.id)]
        found = []
        for product in Product.search(domain):
            size = product._poc_size_mm()
            excess = self._poc_size_excess(requested, given, size, tolerance)
            if excess is not None:
                found.append({"product": product, "size": size, "excess": excess})
        found.sort(key=lambda c: (c["excess"], c["product"].lst_price, c["product"].id))
        return found[: max(template.alternative_limit, 0) or len(found)]

    @api.model
    def _poc_size_excess(self, requested, given, size, tolerance):
        """Сумата на относителните излишъци — или None, ако не става."""
        orientations = [size]
        if len(size) >= 2:
            orientations.append([size[1], size[0], *size[2:]])
        best = None
        for sized in orientations:
            excess = 0.0
            for i in given:
                if i >= len(sized):
                    break
                want, have = requested[i], sized[i]
                if have + EPSILON_MM < want or have > want * (1 + tolerance) + EPSILON_MM:
                    break
                excess += max(have - want, 0.0) / want
            else:
                best = excess if best is None else min(best, excess)
        return best

    # ── Изборът ──────────────────────────────────────────────────────

    def write(self, vals):
        if "standard_product_id" in vals:
            self._poc_check_standard_allowed()
        res = super().write(vals)
        if "standard_product_id" in vals:
            self._poc_apply_standard()
        return res

    def _poc_check_standard_allowed(self):
        for poc in self:
            order = poc.sudo().order_id
            if order and order.state not in ("draft", "sent"):
                raise UserError(self.env._(
                    "%(poc)s: a standard product can be chosen or dropped only "
                    "while the quotation is a draft.",
                    poc=poc.name,
                ))

    def _poc_apply_standard(self):
        """Редът следва избора: готовият продукт или пак изделието.

        Цената е по ценовата листа (``force_price_recomputation``: цената от
        матрицата иначе минава за ръчна). Текстът на конфигурацията се
        забравя — описанието на реда се смята наново от артикула.
        """
        for poc in self:
            line = poc.sudo().sale_line_id
            system = poc.with_context(poc_system=True).sudo()
            if poc.standard_product_id:
                product = poc.standard_product_id
                if not poc.configured_product_id and line.product_id != product:
                    system.configured_product_id = line.product_id
                body = self.env._("Standard product chosen instead of the configuration: %s")
            else:
                product = poc.configured_product_id
                system.configured_product_id = False
                body = self.env._("Back to the configured product: %s")
            if product and line.product_id != product:
                line.product_id = product
                # пресмятането след записа не носи контекста на записа —
                # затова изрично, иначе старата цена минава за ръчна
                line.with_context(force_price_recomputation=True)._compute_price_unit()
            system.sale_description_block = False
            poc._poc_standard_switched()
            poc.message_post(body=body % (product.display_name if product else "-"))
            poc._poc_compute_derived()

    def _poc_standard_switched(self):
        """Кука след смяната на артикула (цената на матрицата забравя своята)."""
        return True

    def _poc_is_standard(self):
        self.ensure_one()
        return bool(self.standard_product_id)
