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
import ast
import graphlib

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


def formula_names(formula):
    """Имената, които формулата чете (ast Load) — за графа на зависимостите
    и за проверката дали входовете ѝ вече имат стойност."""
    try:
        tree = ast.parse(formula or "", mode="exec")
    except SyntaxError:
        return set()
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


class SaleOrderPocTemplate(models.Model):
    """Шаблонът на конфигурацията: кои параметри има видът продукт.

    Схемата на пропъртитата (``param_definition``) не се пише на ръка — тя
    се смята от редовете към речника (ADR sale-order-poc/0002). Запис в нея
    дава грешка, затова уиджетът на Odoo не може да роди параметър със
    случайно име от формата на POC.
    """

    _name = "sale.order.poc.template"
    _description = "Production Configuration Template"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", help="Leave empty to share the template between companies."
    )
    # aspect: шаблон, който се добавя към конкретен POC (стъпка S2)
    usage = fields.Selection(
        [("main", "Product"), ("aspect", "Aspect")],
        required=True,
        default="main",
    )
    line_ids = fields.One2many(
        "sale.order.poc.template.line", "template_id", string="Lines", copy=True
    )
    param_definition = fields.PropertiesDefinition(
        string="Parameters Definition",
        compute="_compute_param_definition",
        store=True,
        readonly=True,
    )
    label_formula = fields.Text(
        help="Formula whose result is the one-line summary of a configuration, "
        "e.g. result = '%sx%s mm' % (width_mm, length_mm)"
    )
    # клиентът одобрява конфигурацията с офертата (ADR sale-order-poc/0017)
    sale_description = fields.Text(
        string="Quotation Text",
        translate=True,
        help="Text added to the description of the sales order line, so the "
        "customer sees and accepts the configuration with the quotation. "
        "Write {{ code }} for a parameter; a line whose parameter is empty is "
        "left out. The text follows the configuration while the quotation is "
        "a draft or sent; a block edited by hand is not overwritten.",
    )
    # аспектите се добавят към конкретен POC (ADR sale-order-poc/0004)
    allowed_aspect_ids = fields.Many2many(
        "sale.order.poc.template",
        "sale_order_poc_template_aspect_rel",
        "template_id",
        "aspect_id",
        string="Allowed Aspects",
        domain=[("usage", "=", "aspect")],
    )
    default_aspect_ids = fields.Many2many(
        "sale.order.poc.template",
        "sale_order_poc_template_default_aspect_rel",
        "template_id",
        "aspect_id",
        string="Default Aspects",
        domain=[("usage", "=", "aspect")],
    )
    poc_ids = fields.One2many("sale.order.poc", "template_id")
    poc_count = fields.Integer(compute="_compute_poc_count")

    _code_uniq = models.Constraint(
        "unique(code)", "The template code must be unique."
    )

    @api.depends(
        "company_id",
        "line_ids",
        "line_ids.sequence",
        "line_ids.display_type",
        "line_ids.name",
        "line_ids.fold",
        "line_ids.param_id",
        "line_ids.param_id.code",
        "line_ids.param_id.name",
        "line_ids.param_id.param_type",
        "line_ids.param_id.suffix",
        "line_ids.param_id.comodel",
        "line_ids.param_id.domain",
        "line_ids.param_id.default_value",
        "line_ids.param_id.option_ids",
        "line_ids.param_id.option_ids.key",
        "line_ids.param_id.option_ids.name",
        "line_ids.param_id.option_ids.color",
    )
    def _compute_param_definition(self):
        # зависимостите са по релационни пътища: depends по съдържанието на
        # PropertiesDefinition не се задейства (l10n_bg_version_block.py:63-68)
        for template in self:
            # jsonb не се превежда ⇒ етикетите са на езика на фирмата
            company = template.company_id or self.env.company
            lang = company.partner_id.lang or "en_US"
            lines = template.with_context(lang=lang).line_ids.sorted(
                lambda line: (line.sequence, line._origin.id or 0)
            )
            definition = []
            for index, line in enumerate(lines):
                if line.display_type == "line_section":
                    # името на разделителя е по позиция: при редакция в
                    # onchange редът още няма id
                    definition.append(
                        {
                            "name": "section_%d" % index,
                            "string": line.name or "",
                            "type": "separator",
                            "fold_by_default": bool(line.fold),
                        }
                    )
                elif line.param_id:
                    # таблиците не влизат в схемата: те са детски редове
                    entry = line.param_id._definition_entry()
                    if entry:
                        definition.append(entry)
            template.param_definition = definition or False

    def _compute_poc_count(self):
        counts = dict(
            self.env["sale.order.poc"]._read_group(
                [("template_id", "in", self.ids)], ["template_id"], ["__count"]
            )
        )
        for template in self:
            template.poc_count = counts.get(template, 0)

    def write(self, vals):
        if "param_definition" in vals:
            # уиджетът пише схемата през write() с правата на потребителя
            # (ORM/fields_properties.py:308-327) — тук е пазачът
            raise UserError(
                self.env._(
                    "Parameters are added through the template lines, not from "
                    "the configuration form."
                )
            )
        return super().write(vals)

    @api.constrains("allowed_aspect_ids", "default_aspect_ids", "line_ids", "usage")
    def _check_aspect_keys(self):
        """Кодовете на основния шаблон и на позволените аспекти не се
        застъпват, нито аспектите помежду си: за формулите пространството е
        едно и плоско (ADR sale-order-poc/0004)."""
        for template in self:
            if not (template.allowed_aspect_ids or template.default_aspect_ids):
                continue
            outside = template.default_aspect_ids - template.allowed_aspect_ids
            if outside:
                raise ValidationError(
                    self.env._(
                        "The default aspects must be allowed first: %(aspects)s",
                        aspects=", ".join(outside.mapped("name")),
                    )
                )
            used = {
                code: template.display_name
                for code in template.line_ids.param_id.mapped("code")
            }
            for aspect in template.allowed_aspect_ids:
                for code in aspect.line_ids.param_id.mapped("code"):
                    if code in used:
                        raise ValidationError(
                            self.env._(
                                "Parameter %(code)s is in %(first)s and in "
                                "%(second)s; an aspect may not repeat a code.",
                                code=code,
                                first=used[code],
                                second=aspect.display_name,
                            )
                        )
                    used[code] = aspect.display_name

    @api.constrains("line_ids", "label_formula")
    def _check_formula_graph(self):
        for template in self:
            template._poc_formula_lines()
            if template.label_formula:
                error = self.env["formula.engine.mixin"]._formula_check(
                    template.label_formula
                )
                if error:
                    raise ValidationError(error)

    def _poc_formula_lines(self):
        """Редовете с формула в реда на зависимостите.

        Цикъл дава ValidationError (ADR sale-order-poc/0002, D17): формулите
        се смятат веднъж, без повторения.
        """
        self.ensure_one()
        return self._poc_order_formula_lines(self.line_ids, self.display_name)

    @api.model
    def _poc_order_formula_lines(self, lines, name):
        """Подрежда редове с формула по зависимости — на един шаблон или на
        основния ∪ аспектите, защото кодовете им са disjoint (ADR 0004)."""
        lines = lines.filtered(lambda line: line.formula and line.param_id)
        by_code = {line.param_id.code: line for line in lines}
        sorter = graphlib.TopologicalSorter()
        for line in lines.sorted(lambda line: (line.sequence, line.id)):
            deps = line._formula_names() & by_code.keys()
            deps.discard(line.param_id.code)
            sorter.add(line.param_id.code, *sorted(deps))
        try:
            order = list(sorter.static_order())
        except graphlib.CycleError as exc:
            raise ValidationError(
                self.env._(
                    "The formulas of template %(template)s depend on each other in "
                    "a circle: %(cycle)s",
                    template=name,
                    cycle=" → ".join(exc.args[1]),
                )
            ) from exc
        return [by_code[code] for code in order if code in by_code]

    def action_recompute_draft_pocs(self):
        """Преизчислява изчислените параметри на черновите конфигурации."""
        pocs = self.poc_ids.filtered(lambda p: p.state == "draft")
        pocs._poc_compute_derived()
        return True

    def action_view_pocs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_order_poc.sale_order_poc_action"
        )
        action["domain"] = [("template_id", "=", self.id)]
        return action


class SaleOrderPocTemplateLine(models.Model):
    """Ред на шаблона: параметър от речника (или заглавие на секция).

    Празна формула — входен параметър. Попълнена — изчислен; тогава
    ``allow_manual`` и ``allow_fallback`` казват дали стойността може да се
    поправи на ръка и какво става, ако формулата гръмне (ADR
    sale-order-poc/0003).
    """

    _name = "sale.order.poc.template.line"
    _description = "Production Configuration Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "sale.order.poc.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([("line_section", "Section")])
    name = fields.Char(string="Section", translate=True)
    fold = fields.Boolean(string="Folded")
    param_id = fields.Many2one(
        "sale.order.poc.param", string="Parameter", ondelete="restrict"
    )
    code = fields.Char(related="param_id.code")
    param_type = fields.Selection(related="param_id.param_type")
    required = fields.Boolean(
        help="The configuration cannot go to production without this value."
    )
    formula = fields.Text(
        help="Python code that assigns result. Other parameters are available "
        "by their code, plus poc, poc_product, order_qty and order_uom."
    )
    allow_manual = fields.Boolean(
        string="Manual Override",
        help="A user may overwrite the computed value; it then stays until "
        "reset to the formula.",
    )
    allow_fallback = fields.Boolean(
        string="Keep Value on Error",
        help="If the formula fails, the last value stays and a warning is "
        "logged on the configuration instead of an error.",
    )

    _param_uniq = models.Constraint(
        "unique(template_id, param_id)",
        "A parameter can appear only once in a template.",
    )

    @api.constrains(
        "display_type", "param_id", "formula", "required", "allow_manual",
        "allow_fallback",
    )
    def _check_line(self):
        engine = self.env["formula.engine.mixin"]
        for line in self:
            if line.display_type == "line_section":
                if line.param_id or line.formula:
                    raise ValidationError(
                        self.env._("A section line has no parameter or formula.")
                    )
                continue
            if not line.param_id:
                raise ValidationError(self.env._("A template line needs a parameter."))
            if line.formula:
                if line.param_type == "table":
                    raise ValidationError(
                        self.env._(
                            "Parameter %(code)s is a table; it is filled by rows, "
                            "not by a formula.",
                            code=line.param_id.code,
                        )
                    )
                if line.required:
                    raise ValidationError(
                        self.env._(
                            "Parameter %(code)s is computed; it cannot be required.",
                            code=line.param_id.code,
                        )
                    )
                error = engine._formula_check(line.formula)
                if error:
                    raise ValidationError(error)
            elif line.allow_manual or line.allow_fallback:
                raise ValidationError(
                    self.env._(
                        "Manual override and keeping the value on error apply "
                        "only to computed parameters (%(code)s).",
                        code=line.param_id.code,
                    )
                )
        # ограничението на шаблона не се задейства, когато ред се създава
        # направо — цикълът се хваща и оттук
        for template in self.template_id:
            template._poc_formula_lines()

    def _formula_names(self):
        self.ensure_one()
        return formula_names(self.formula)
