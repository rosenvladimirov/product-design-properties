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
import math
import re

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from .poc_template import formula_names

STATE_BY_ORDER_STATE = {
    "draft": "draft",
    "sent": "draft",
    "sale": "confirmed",
    "cancel": "cancel",
}

PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")

# потребителските полета; системните (лот, произход, резюме) минават с
# контекст poc_system (ADR sale-order-poc/0009)
USER_FIELDS = frozenset(
    {"params", "template_id", "note", "aspect_ids", "line_ids"}
)


def _is_empty(value):
    """Липса на стойност: None, False, празен низ или списък, празен запис.

    Нулата е стойност (фонд на 0,00 % е законен).
    """
    if value is None or value is False:
        return True
    if isinstance(value, (str, list, tuple)) and not value:
        return True
    if isinstance(value, models.BaseModel) and not value:
        return True
    return False


class SaleOrderPoc(models.Model):
    """Конфигурацията на производството за един ред на продажбата.

    Сделката е в колони, спецификацията — в пропъртита по шаблона (ADR
    sale-order-poc/0001). Входовете и изчислените параметри са в една група
    ``params``; произходът на изчислените (формула или ръчно) е в
    ``param_origins`` (ADR sale-order-poc/0003).

    Параметрите се четат само през ``_poc_values()`` и се пишат само през
    ``_poc_set_params()``: ``record.params[k]`` дава етикета на селекцията и
    False вместо 0, а запис на dict заменя всички стойности.
    """

    _name = "sale.order.poc"
    _description = "Production Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        copy=False,
        readonly=True,
        index="trigram",
        default=lambda self: self.env._("New"),
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Order Line",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
        check_company=True,
    )
    order_id = fields.Many2one(
        related="sale_line_id.order_id", store=True, index=True, string="Order"
    )
    partner_id = fields.Many2one(related="order_id.partner_id", store=True)
    product_id = fields.Many2one(related="sale_line_id.product_id", store=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
    product_uom_qty = fields.Float(related="sale_line_id.product_uom_qty")
    product_uom_id = fields.Many2one(related="sale_line_id.product_uom_id")
    template_id = fields.Many2one(
        "sale.order.poc.template",
        string="Template",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('usage', '=', 'main'), ('company_id', 'in', [False, company_id])]",
    )
    params = fields.Properties(
        string="Parameters",
        definition="template_id.param_definition",
        copy=True,
    )
    param_origins = fields.Json(copy=True, readonly=True)
    # разширенията на носителя (ADR sale-order-poc/0004)
    aspect_ids = fields.One2many(
        "sale.order.poc.aspect", "poc_id", string="Aspects", copy=True
    )
    line_ids = fields.One2many(
        "sale.order.poc.line", "poc_id", string="Table Rows", copy=True
    )
    table_count = fields.Integer(compute="_compute_table_count")
    manual_params = fields.Char(
        string="Manual Values",
        compute="_compute_manual_params",
        help="Computed parameters overwritten by hand; the formula leaves them.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("cancel", "Cancelled")],
        compute="_compute_state",
        store=True,
        index=True,
        tracking=True,
    )
    lot_id = fields.Many2one("stock.lot", string="Lot", readonly=True, copy=False)
    lot_ids = fields.One2many("stock.lot", "poc_id", string="Lots")
    lot_count = fields.Integer(compute="_compute_lot_count")
    summary = fields.Char(readonly=True, copy=False, index="trigram")
    # последно вписаният блок в описанието на реда (ADR sale-order-poc/0017)
    sale_description_block = fields.Text(readonly=True, copy=False)
    note = fields.Html(string="Special Requirements")
    can_edit_confirmed = fields.Boolean(compute="_compute_can_edit_confirmed")
    release_needed = fields.Boolean(compute="_compute_release_needed")

    _sale_line_uniq = models.Constraint(
        "unique(sale_line_id)", "An order line has one production configuration."
    )

    # ── Компютове ────────────────────────────────────────────────────

    @api.depends("sale_line_id.order_id.state")
    def _compute_state(self):
        for poc in self:
            poc.state = STATE_BY_ORDER_STATE.get(poc.order_id.state, "draft")

    @api.depends("name", "summary")
    def _compute_display_name(self):
        for poc in self:
            poc.display_name = (
                "%s · %s" % (poc.name, poc.summary) if poc.summary else poc.name
            )

    @api.depends("param_origins", "template_id")
    def _compute_manual_params(self):
        for poc in self:
            names = []
            for container in poc._poc_containers():
                origins = container.param_origins or {}
                names += [
                    line.param_id.name
                    for line in container.template_id.line_ids
                    if line.param_id and origins.get(line.param_id.code) == "manual"
                ]
            poc.manual_params = ", ".join(names) or False

    def _compute_table_count(self):
        for poc in self:
            poc.table_count = len(poc._poc_table_params())

    def _compute_lot_count(self):
        for poc in self:
            poc.lot_count = len(poc.lot_ids)

    @api.depends_context("uid")
    def _compute_can_edit_confirmed(self):
        allowed = self.env.user.has_group("sale_order_poc.group_poc_manager")
        for poc in self:
            poc.can_edit_confirmed = allowed

    @api.depends("state", "sale_line_id.move_ids")
    def _compute_release_needed(self):
        for poc in self:
            poc.release_needed = (
                poc.state == "confirmed"
                and poc.product_id.type == "consu"
                and not poc.sale_line_id.move_ids
            )

    # ── Четецът и писачът ────────────────────────────────────────────

    def _poc_values(self):
        """ЕДИНСТВЕНИЯТ четец: {код: стойност}.

        Числата са числа (0 е 0), селекцията е КЛЮЧ, таговете са списък
        ключове, m2o/m2m са записи, датата е date, липсата е None. Вика
        ``convert_to_read_multi(use_display_name=False)`` — както
        ``Property.__getitem__`` (ORM/fields_properties.py:815-819), но без
        неговите етикет вместо ключ и False вместо 0 (:829-838).
        """
        self.ensure_one()
        values = {}
        for container in self._poc_containers():
            values.update(self._poc_read_properties(container, "params"))
        values.update(self._poc_table_values())
        return values

    def _poc_containers(self):
        """Носителите на стойности: основният и по един на аспект.

        Properties има точно един контейнер на запис
        (ORM/fields_properties.py:401-405), затова аспектът е отделен ред
        (ADR sale-order-poc/0004). Кодовете им са disjoint, така че за
        формулите пространството е едно.
        """
        self.ensure_one()
        return [self] + list(self.aspect_ids)

    def _poc_params(self):
        """Всички параметри на конфигурацията: основният шаблон и аспектите."""
        self.ensure_one()
        lines = self.template_id.line_ids | self.aspect_ids.template_id.line_ids
        return lines.param_id

    def _poc_table_params(self):
        """Параметрите тип таблица на основния шаблон и на аспектите."""
        self.ensure_one()
        lines = self.template_id.line_ids | self.aspect_ids.template_id.line_ids
        return lines.param_id.filtered(lambda param: param.param_type == "table")

    def _poc_table_values(self):
        """Таблиците в договора: {код: [{key, product, value, uom}…]}.

        Празната клетка е липсващ ред, не нула; редът е по sequence.
        """
        self.ensure_one()
        tables = {param.code: [] for param in self._poc_table_params()}
        # изрично по sequence: след create редовете са в кеша по ред на
        # създаване, а договорът обещава подредба
        for line in self.line_ids.sorted(lambda line: (line.sequence, line.id)):
            if line.param_id.code in tables:
                tables[line.param_id.code].append(
                    {
                        "key": line.key,
                        "product": line.product_id,
                        "value": line.value,
                        "uom": line.uom_id,
                    }
                )
        return tables

    @api.model
    def _poc_read_properties(self, record, field_name):
        field = record._fields[field_name]
        props = field.convert_to_read_multi(
            [record[field_name]], record, use_display_name=False
        )[0]
        return {
            prop["name"]: self._poc_decode(prop)
            for prop in props
            if prop.get("type") != "separator"
        }

    @api.model
    def _poc_decode(self, prop):
        ptype = prop.get("type")
        value = prop.get("value")
        comodel = prop.get("comodel")
        if ptype in ("many2one", "many2many"):
            if not comodel or comodel not in self.env:
                return None
            model = self.env[comodel]
            if ptype == "many2one":
                return model.browse(value) if value else model
            return model.browse(value or [])
        if value is None:
            return None
        if ptype == "date":
            return fields.Date.to_date(value) if value else None
        if ptype == "tags":
            return list(value or [])
        if ptype == "boolean":
            return bool(value)
        return value

    @api.model
    def _poc_encode(self, ptype, value):
        """Стойност от формула или код → суровия вид на пропъртито."""
        if value is None:
            return None
        if ptype == "many2one":
            if isinstance(value, models.BaseModel):
                return value[:1].id or False
            return value or False
        if ptype == "many2many":
            if isinstance(value, models.BaseModel):
                return value.ids
            return list(value or [])
        if ptype == "date" and isinstance(value, datetime.date):
            return fields.Date.to_string(value)
        if ptype == "tags":
            return list(value or [])
        return value

    def _poc_set_params(self, updates):
        """ЕДИНСТВЕНИЯТ писач: {**сурови, **нови}.

        Запис на dict заменя всички стойности (ORM/fields_properties.py:
        304-306), затова заварените се четат сурови (id-та, не записи) и
        новите се сливат отгоре. Кодове извън схемата се пропускат.
        """
        for poc in self:
            for container in poc._poc_containers():
                types = {
                    entry["name"]: entry["type"]
                    for entry in (container.template_id.param_definition or [])
                }
                mine = {code: v for code, v in updates.items() if code in types}
                if not mine:
                    continue
                raw = dict(container.params._values or {})
                for code, value in mine.items():
                    raw[code] = poc._poc_encode(types[code], value)
                container.params = raw

    # ── Раждане ──────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        new_name = self.env._("New")
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == new_name:
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("sale.order.poc") or new_name
                )
            if not vals.get("template_id") and vals.get("sale_line_id"):
                line = self.env["sale.order.line"].browse(vals["sale_line_id"])
                template = line.product_id.product_tmpl_id.poc_template_id
                if template:
                    vals["template_id"] = template.id
        pocs = super(SaleOrderPoc, self.with_context(poc_system=True)).create(
            vals_list
        )
        for poc, vals in zip(pocs, vals_list, strict=True):
            if "aspect_ids" not in vals and poc.template_id.default_aspect_ids:
                # аспектите по подразбиране на шаблона (ADR sale-order-poc/0004)
                self.env["sale.order.poc.aspect"].with_context(
                    poc_system=True
                ).create(
                    [
                        {"poc_id": poc.id, "template_id": aspect.id}
                        for aspect in poc.template_id.default_aspect_ids
                    ]
                )
            if "params" not in vals:
                poc._poc_apply_defaults()
        pocs._poc_compute_derived()
        return pocs.with_env(self.env)

    def _poc_apply_defaults(self):
        """Подразбиранията се пишат изрично, включително нулата.

        ORM прилага само истинно подразбиране от схемата
        (ORM/fields_properties.py:388-397). Редът е: речникът, после
        константите на продукта (``poc_default_params``).
        """
        self.ensure_one()
        for container in self._poc_containers():
            defaults = {}
            for line in container.template_id.line_ids.filtered("param_id"):
                value = line.param_id._parse_default()
                if value is not None:
                    defaults[line.param_id.code] = value
            if container == self:
                product_tmpl = self.product_id.product_tmpl_id
                if product_tmpl.poc_template_id == self.template_id:
                    product_values = product_tmpl.poc_default_params._values or {}
                    defaults.update(
                        {code: v for code, v in product_values.items() if v is not None}
                    )
            if defaults:
                raw = dict(container.params._values or {})
                raw.update(defaults)
                container.with_context(poc_system=True).params = raw

    # ── Stage 1: изчислените параметри ───────────────────────────────

    def _poc_formula_context(self):
        """Договорът на Stage 1 без стойностите: без ``env`` (ADR
        sale-order-poc/0005); продуктът на POC е ``poc_product``."""
        self.ensure_one()
        return {
            "poc": self,
            "poc_product": self.product_id,
            "order_qty": self.product_uom_qty,
            "order_uom": self.product_uom_id,
            "ceil": math.ceil,
            "floor": math.floor,
            "sqrt": math.sqrt,
            "pi": math.pi,
        }

    def _poc_compute_derived(self):
        """Смята изчислените параметри в реда на зависимостите.

        Всяка формула получава СВОЕ копие на контекста: safe_eval мутира
        подадения dict (base_formula_engine), а временна променлива на една
        формула не бива да засенчи вход на друга. Ръчна стойност при
        ``allow_manual`` не се пресмята. При грешка: ``allow_fallback`` —
        стойността остава и в чатъра отива предупреждение; иначе UserError
        (ADR sale-order-poc/0003).
        """
        engine = self.env["formula.engine.mixin"]
        Template = self.env["sale.order.poc.template"]
        for poc in self:
            template = poc.template_id
            containers = poc._poc_containers()
            all_lines = self.env["sale.order.poc.template.line"].browse()
            for container in containers:
                all_lines |= container.template_id.line_ids
            lines = Template._poc_order_formula_lines(all_lines, poc.display_name)
            if not lines and not template.label_formula:
                continue
            # всеки ред пише в своя контейнер: основният шаблон или аспектът
            container_by_template = {
                container.template_id: container for container in containers
            }
            values = poc._poc_values()
            origins = {
                container: dict(container.param_origins or {})
                for container in containers
            }
            base = poc._poc_formula_context()
            updates = {}
            fallbacks = []
            for line in lines:
                code = line.param_id.code
                container = container_by_template[line.template_id]
                if line.allow_manual and origins[container].get(code) == "manual":
                    continue
                if poc._poc_inputs_missing(line.formula, values):
                    # входовете още ги няма (черновата се попълва): изходът е
                    # празен, не грешка; задължителните се проверяват при
                    # потвърждаване, преди Stage 1
                    if values.get(code) is not None:
                        values[code] = None
                        updates[code] = None
                    origins[container].pop(code, None)
                    continue
                try:
                    result = engine._formula_eval(
                        line.formula, {**base, **values}, strict=True
                    )["result"]
                    result = line.param_id._poc_coerce(result)
                except Exception as exc:  # политиката е по ред на шаблона
                    if line.allow_fallback:
                        fallbacks.append((line.param_id.name, str(exc)))
                        continue
                    raise UserError(
                        self.env._(
                            "Parameter %(param)s of %(poc)s: %(error)s",
                            param=code,
                            poc=poc.name,
                            error=exc,
                        )
                    ) from exc
                values[code] = result
                updates[code] = result
                origins[container][code] = "formula"
            summary = poc.summary
            if template.label_formula and poc._poc_inputs_missing(
                template.label_formula, values
            ):
                summary = False
            elif template.label_formula:
                try:
                    summary = engine._formula_eval(
                        template.label_formula, {**base, **values}, strict=True
                    )["result"]
                except Exception as exc:
                    raise UserError(
                        self.env._(
                            "Summary formula of template %(template)s: %(error)s",
                            template=template.display_name,
                            error=exc,
                        )
                    ) from exc
                summary = False if _is_empty(summary) else str(summary)
            system = poc.with_context(poc_system=True)
            if updates:
                system._poc_set_params(updates)
            for container, container_origins in origins.items():
                if container_origins != (container.param_origins or {}):
                    container.with_context(poc_system=True).param_origins = (
                        container_origins
                    )
            if summary != poc.summary:
                system.write({"summary": summary})
            if fallbacks:
                poc.message_post(
                    body=Markup("<p>%s</p><ul>%s</ul>")
                    % (
                        self.env._("A formula failed; the last value was kept:"),
                        Markup().join(
                            Markup("<li>%s: %s</li>") % (name, error)
                            for name, error in fallbacks
                        ),
                    )
                )
        # извън цикъла: шаблон без формули също има текст за офертата
        self._poc_apply_sale_description()

    # ── Текстът в офертата ───────────────────────────────────────────

    def _poc_apply_sale_description(self):
        """Вписва текста на шаблона в описанието на реда на продажбата.

        Клиентът одобрява конфигурацията, като приеме офертата, затова тя
        трябва да се вижда в самата оферта (ADR sale-order-poc/0017).
        Текстът следва конфигурацията, докато офертата е чернова или
        изпратена; потвърдената носи одобрения текст и не се пипа.

        Помни се последно вписаният блок. Намери ли се в описанието, се
        подменя, а текстът около него остава. Не се ли намери, някой го е
        редактирал на ръка — тогава не се презаписва, а в чатъра отива
        бележка, че офертата не следва конфигурацията.
        """
        for poc in self:
            # системен запис като лота и резюмето: правото идва от записа на
            # POC; продавач може да пише POC на поръчка, която не може да чете
            line = poc.sudo().sale_line_id
            if not line or line.order_id.state not in ("draft", "sent"):
                continue
            # на езика на клиента, както ядрото пише описанието на реда
            lang = line.order_id._get_lang()
            poc_lang = poc.with_context(lang=lang)
            text = poc_lang.template_id.sale_description
            block = poc_lang._poc_render(text).strip() if text else ""
            old = poc.sale_description_block or ""
            if block == old:
                continue
            name = line.name or ""
            if old and old not in name:
                poc.message_post(
                    body=self.env._(
                        "The quotation text of this configuration was edited by "
                        "hand, so it was not updated. The quotation no longer "
                        "follows the configuration."
                    )
                )
                continue
            if old:
                name = name.replace(old, block, 1)
                if not block:
                    name = name.rstrip()
            elif block:
                name = f"{name.rstrip()}\n\n{block}" if name.strip() else block
            line.name = name
            poc.with_context(poc_system=True).sale_description_block = block or False

    @api.model
    def _poc_inputs_missing(self, formula, values):
        """Формулата чете параметър без стойност (None)."""
        return any(
            values.get(name) is None for name in formula_names(formula) & values.keys()
        )

    # ── Текст по конфигурацията ──────────────────────────────────────

    def _poc_render(self, text, fmt="markdown", extra=None):
        """``{{ код }}`` → стойността, БЕЗ eval.

        Ред, в който някой заместител е празен, изпада целият: бележката за
        цеха не бива да показва „Цвят:“ без цвят. Селекцията излиза с
        етикета си, числото — закръглено и със суфикса на параметъра.
        ``fmt='html'`` ескейпва стойностите.
        """
        self.ensure_one()
        if not text:
            return ""
        values = {**self._poc_values(), **(extra or {})}
        params = {param.code: param for param in self._poc_params()}
        rendered = []
        for line in text.splitlines():
            codes = PLACEHOLDER.findall(line)
            if codes and any(_is_empty(values.get(code)) for code in codes):
                continue
            rendered.append(
                PLACEHOLDER.sub(
                    lambda match: self._poc_render_value(
                        params.get(match.group(1)), values.get(match.group(1)), fmt
                    ),
                    line,
                )
            )
        return "\n".join(rendered)

    @api.model
    def _poc_render_value(self, param, value, fmt):
        """Стойността, както я чете човек: етикет, закръгляне, суфикс."""
        if isinstance(value, models.BaseModel):
            text = ", ".join(value.mapped("display_name"))
        elif param and param.param_type == "selection":
            options = {option.key: option.name for option in param.option_ids}
            text = options.get(value, "" if value is None else str(value))
        elif param and param.param_type == "tags":
            options = {option.key: option.name for option in param.option_ids}
            text = ", ".join(options.get(key, key) for key in value or [])
        elif param and param.param_type == "float" and isinstance(value, (int, float)):
            text = ("%%.%df" % max(param.digits, 0)) % value
            text = text.rstrip("0").rstrip(".") if "." in text else text
        elif param and param.param_type == "boolean":
            # „True“ не е текст за клиента; лъжата изпада с реда си
            text = self.env._("Yes") if value else ""
        elif value is None or value is False:
            text = ""
        else:
            text = str(value)
        if text and param and param.suffix:
            text = "%s %s" % (text, param.suffix)
        return escape(text) if fmt == "html" else text

    # ── Редакция ─────────────────────────────────────────────────────

    def write(self, vals):
        if self.env.context.get("poc_system"):
            return super().write(vals)
        if USER_FIELDS & vals.keys():
            self._poc_check_can_edit(vals)
        watch = "params" in vals or "template_id" in vals
        before = {poc.id: poc._poc_values() for poc in self} if watch else {}
        confirmed = self.filtered(lambda p: p.state != "draft") if watch else self
        res = super().write(vals)
        if "params" in vals and "template_id" not in vals:
            for poc in self:
                poc._poc_mark_manual(before[poc.id])
        if watch:
            self._poc_compute_derived()
            for poc in confirmed:
                poc._poc_post_changes(before[poc.id])
        return res

    def _poc_check_can_edit(self, vals):
        confirmed = self.filtered(lambda p: p.state != "draft")
        if not confirmed:
            return
        if "template_id" in vals:
            raise UserError(
                self.env._(
                    "The template of a confirmed configuration cannot change: %(pocs)s",
                    pocs=", ".join(confirmed.mapped("name")),
                )
            )
        if not self.env.user.has_group("sale_order_poc.group_poc_manager"):
            raise UserError(
                self.env._(
                    "Only a production configuration manager can change a "
                    "confirmed configuration: %(pocs)s",
                    pocs=", ".join(confirmed.mapped("name")),
                )
            )

    def _poc_check_children_editable(self):
        """Аспектите и редовете на таблиците са потребителски данни: след
        потвърждаване ги мени само мениджър (ADR sale-order-poc/0009)."""
        if self.env.context.get("poc_system"):
            return
        self._poc_check_can_edit({"aspect_ids": True})

    def _poc_mark_manual(self, before):
        """Потребител смени изчислен параметър: ръчен или грешка."""
        self.ensure_one()
        after = self._poc_values()
        for container in self._poc_containers():
            origins = dict(container.param_origins or {})
            changed = False
            for line in container.template_id.line_ids:
                if not (line.formula and line.param_id):
                    continue
                code = line.param_id.code
                if after.get(code) == before.get(code):
                    continue
                if not line.allow_manual:
                    # пропъртитата нямат „само за четене“ по ключ — забраната е тук
                    raise UserError(
                        self.env._(
                            "%(param)s is computed by a formula and cannot be edited.",
                            param=line.param_id.name,
                        )
                    )
                origins[code] = "manual"
                changed = True
            if changed:
                container.with_context(poc_system=True).param_origins = origins

    def _poc_post_changes(self, before):
        """Разликата „код: старо → ново“ в чатъра на потвърдена конфигурация
        (Properties нямат tracking)."""
        self.ensure_one()
        after = self._poc_values()
        lines = []
        for code in sorted(set(before) | set(after)):
            old, new = before.get(code), after.get(code)
            if old == new:
                continue
            lines.append(
                Markup("<li>%s: %s → %s</li>")
                % (code, self._poc_display(old), self._poc_display(new))
            )
        if lines:
            self.message_post(
                body=Markup("<p>%s</p><ul>%s</ul>")
                % (self.env._("Parameters changed:"), Markup().join(lines))
            )

    @api.model
    def _poc_display(self, value):
        if _is_empty(value) and value != 0:
            return "—"
        if isinstance(value, models.BaseModel):
            return ", ".join(value.mapped("display_name"))
        return str(value)

    def unlink(self):
        if any(poc.state != "draft" for poc in self):
            raise UserError(
                self.env._("Only a draft production configuration can be deleted.")
            )
        return super().unlink()

    # ── Към производството ───────────────────────────────────────────

    def _poc_check_required(self):
        for poc in self:
            values = poc._poc_values()
            missing = []
            for container in poc._poc_containers():
                missing += [
                    line.param_id.name
                    for line in container.template_id.line_ids
                    if line.required
                    and line.param_id
                    and line.param_id.param_type != "boolean"
                    and _is_empty(values.get(line.param_id.code))
                ]
            if missing:
                raise UserError(
                    self.env._(
                        "%(poc)s is missing required parameters: %(params)s",
                        poc=poc.name,
                        params=", ".join(missing),
                    )
                )

    def _poc_confirm(self):
        """Точно преди процюърмънта: задължителните, Stage 1, лотът.

        Вика се от ``sale.order.line._action_launch_stock_rule``. Всичко е
        системен запис: продавач без права на мениджър също потвърждава.
        """
        system = self.with_context(poc_system=True)
        system._poc_check_required()
        system._poc_compute_derived()
        system._poc_ensure_lot()

    def _poc_ensure_lot(self):
        for poc in self:
            product = poc.product_id
            if product.is_storable and product.tracking == "lot" and not poc.lot_id:
                poc._poc_lot(product)

    def _poc_lot(self, product, new_batch=False):
        """ЕДИНСТВЕНИЯТ създател на лотове на конфигурацията.

        Семейството е stock.lot(poc_id, product_id); връща партидата с най-
        голям номер или ражда следващата. Името идва от куката
        ``_poc_lot_name``; без нея — от поредността на продукта (префиксът
        му), а продукт без поредност взима стандартната на Odoo „Serial
        Numbers“ (ADR sale-order-poc/0013).
        """
        self.ensure_one()
        Lot = self.env["stock.lot"].sudo()
        last = Lot.search(
            [("poc_id", "=", self.id), ("product_id", "=", product.id)],
            order="poc_batch desc, id desc",
            limit=1,
        )
        if last and not new_batch:
            return last.with_env(self.env)
        number = (last.poc_batch or 0) + 1
        vals = {
            "product_id": product.id,
            "poc_id": self.id,
            "poc_batch": number,
            "ref": self.name,
            "company_id": self.company_id.id,
        }
        name = self._poc_lot_name(product, number)
        if not name and not product.lot_sequence_id:
            # stock.lot._compute_name чете само поредността на продукта; по
            # код не се търси — поредностите с префикс също са stock.lot.serial
            standard = self.env.ref(
                "stock.sequence_production_lots", raise_if_not_found=False
            )
            name = standard.sudo().next_by_id() if standard else False
            if not name:
                raise UserError(
                    self.env._(
                        "No lot sequence for %(product)s: set a lot prefix on the "
                        "product.",
                        product=product.display_name,
                    )
                )
        if name:
            taken = Lot.search_count(
                [
                    ("product_id", "=", product.id),
                    ("name", "=", name),
                    ("company_id", "in", [False, self.company_id.id]),
                ]
            )
            if taken:
                raise UserError(
                    self.env._(
                        "Lot %(lot)s of %(product)s already exists.",
                        lot=name,
                        product=product.display_name,
                    )
                )
            vals["name"] = name
        lot = Lot.create(vals)
        if number == 1 and product == self.product_id and not self.lot_id:
            self.with_context(poc_system=True).lot_id = lot
        return lot.with_env(self.env)

    def _poc_lot_name(self, product, number):
        """Кука за фирма със свое правило за име на лота; False — стандартното."""
        return False

    # ── Бутони ───────────────────────────────────────────────────────

    def action_compute(self):
        self._poc_compute_derived()
        return True

    def action_reset_to_formula(self):
        for poc in self:
            origins = {
                code: "formula"
                for code, origin in (poc.param_origins or {}).items()
            }
            poc.with_context(poc_system=True).write({"param_origins": origins})
        self._poc_compute_derived()
        return True

    def action_release(self):
        """Ред, добавен към вече потвърдена поръчка, тръгва към склада."""
        for poc in self:
            if poc.state != "confirmed":
                raise UserError(
                    self.env._("Only a confirmed configuration can be released.")
                )
            poc.sale_line_id._action_launch_stock_rule()
        return True

    def action_view_lots(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_production_lot_form"
        )
        action["domain"] = [("poc_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
