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
import keyword
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PARAM_TYPES = [
    ("boolean", "Checkbox"),
    ("integer", "Integer"),
    ("float", "Decimal"),
    ("char", "Text"),
    ("text", "Long Text"),
    ("date", "Date"),
    ("selection", "Selection"),
    ("tags", "Tags"),
    ("many2one", "Record"),
    ("many2many", "Records"),
    # таблицата не е пропърти: обявява детски редове (ADR sale-order-poc/0004)
    ("table", "Table"),
]

CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
KEY_RE = re.compile(r"^[a-z0-9_]+$")

# Имената, които формулите виждат като свои: базовият договор на PDP
# (``mrp_bom_line_formula_template``), договорът на POC, помощниците и
# имената на бъдещите адаптери. PDP слива контекста СЛЕД базовите ключове,
# така че параметър ``product`` би подменил компонента на всеки формулен ред
# (ADR sale-order-poc/0002).
POC_RESERVED_NAMES = frozenset(
    {
        # PDP
        "bom_line",
        "operation",
        "product",
        "product_uom",
        "product_uom_qty",
        "production",
        "quantity",
        "result",
        "skip",
        "uom",
        "add_products",
        "env",
        "design_context",
        # договорът на POC
        "poc",
        "poc_product",
        "lot",
        "order_qty",
        "order_uom",
        "mo_qty",
        "mo_uom",
        "mo_product",
        "qty_produced",
        "qty_remaining",
        "template",
        # помощници
        "ceil",
        "floor",
        "sqrt",
        "round",
        "min",
        "max",
        "abs",
        "sum",
        "pi",
        # бъдещи адаптери (forced_lot, операционни формули)
        "forced_lots",
        "lot_model",
        "mo_forced_lots",
        "workorder",
        "duration",
        "employees",
        "materials",
    }
)


class SaleOrderPocParam(models.Model):
    """Речникът на параметрите: един код е един тип в цялата база.

    Кодът е едновременно име на пропърти в схемата на шаблона и име на
    променлива във формулите (ADR sale-order-poc/0002). Мярката е част от
    кода (``width_mm``); ``suffix`` е само за показ.
    """

    _name = "sale.order.poc.param"
    _description = "Production Configuration Parameter"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(string="Label", required=True, translate=True)
    param_type = fields.Selection(
        PARAM_TYPES, string="Type", required=True, default="float"
    )
    option_ids = fields.One2many(
        "sale.order.poc.param.option", "param_id", string="Options", copy=True
    )
    comodel = fields.Char(
        string="Model",
        help="Technical name of the model of a Record or Records parameter, "
        "e.g. product.product.",
    )
    domain = fields.Char(help="Domain limiting the records a user can choose.")
    suffix = fields.Char(
        translate=True,
        help="Shown after the value, e.g. mm. The unit belongs in the code as "
        "well (width_mm); the suffix is display only.",
    )
    digits = fields.Integer(
        default=6,
        help="Decimals a formula result of a Decimal parameter is rounded to.",
    )
    default_value = fields.Char(
        string="Default",
        help="Value a new configuration starts with. Zero is a value. "
        "Selection: the option key. Tags: keys separated by commas. "
        "Record: an XML id or a database id.",
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    template_line_ids = fields.One2many(
        "sale.order.poc.template.line", "param_id", string="Template Lines"
    )

    _code_uniq = models.Constraint(
        "unique(code)", "The parameter code must be unique."
    )

    @api.constrains("code")
    def _check_code(self):
        for param in self:
            code = param.code or ""
            if not CODE_RE.match(code):
                raise ValidationError(
                    self.env._(
                        "The code %(code)s must start with a lowercase letter and "
                        "contain only lowercase letters, digits and underscores.",
                        code=code,
                    )
                )
            if keyword.iskeyword(code) or code in POC_RESERVED_NAMES:
                raise ValidationError(
                    self.env._(
                        "The code %(code)s is reserved: formulas already use "
                        "this name.",
                        code=code,
                    )
                )
            if code.endswith("_html"):
                raise ValidationError(
                    self.env._("The code %(code)s may not end with _html.", code=code)
                )

    @api.constrains("param_type", "comodel")
    def _check_comodel(self):
        for param in self:
            if param.param_type not in ("many2one", "many2many"):
                continue
            model = param.comodel
            if (
                not model
                or model not in self.env
                or self.env[model].is_transient()
                or self.env[model]._abstract
            ):
                raise ValidationError(
                    self.env._(
                        "Parameter %(code)s needs a valid model.", code=param.code
                    )
                )

    def write(self, vals):
        if {"code", "param_type"} & vals.keys():
            used = self.filtered(
                lambda p: p.template_line_ids
                and (
                    ("code" in vals and vals["code"] != p.code)
                    or ("param_type" in vals and vals["param_type"] != p.param_type)
                )
            )
            if used:
                # преименуване оставя стойностите сираци, а group_by взима
                # първата схема с това име в цялата таблица
                raise UserError(
                    self.env._(
                        "The code or the type of a parameter used in a template "
                        "cannot change: %(codes)s",
                        codes=", ".join(used.mapped("code")),
                    )
                )
        return super().write(vals)

    # ── Схемата ──────────────────────────────────────────────────────

    def _definition_entry(self):
        """Записът на параметъра в схемата на шаблона.

        Само позволените ключове на ``PropertiesDefinition``
        (ORM/fields_properties.py:857-861): ключ извън тях сваля
        зареждането на базата. Етикетите са на езика от контекста.
        """
        self.ensure_one()
        if self.param_type == "table":
            return None
        entry = {"name": self.code, "string": self.name, "type": self.param_type}
        if self.param_type == "selection":
            entry["selection"] = [[o.key, o.name] for o in self.option_ids]
        elif self.param_type == "tags":
            # таговете са тройки; двойка сваля валидацията (:1054-1058)
            entry["tags"] = [[o.key, o.name, o.color or 0] for o in self.option_ids]
        elif self.param_type in ("many2one", "many2many"):
            entry["comodel"] = self.comodel
            if self.domain:
                entry["domain"] = self.domain
        if self.suffix:
            entry["suffix"] = self.suffix
        default = self._parse_default()
        if default not in (None, False, "", []):
            entry["default"] = default
        return entry

    def _parse_default(self):
        """``default_value`` в суровия вид на пропъртито; 0 остава 0."""
        self.ensure_one()
        raw = (self.default_value or "").strip()
        if not raw:
            return None
        ptype = self.param_type
        if ptype == "table":
            return None
        try:
            if ptype == "boolean":
                return raw.lower() in ("1", "true", "yes", "y")
            if ptype == "integer":
                return int(raw)
            if ptype == "float":
                return float(raw)
            if ptype == "date":
                return fields.Date.to_string(fields.Date.to_date(raw))
            if ptype == "selection":
                return raw if raw in self.option_ids.mapped("key") else None
            if ptype == "tags":
                keys = set(self.option_ids.mapped("key"))
                return [k.strip() for k in raw.split(",") if k.strip() in keys]
            if ptype in ("many2one", "many2many"):
                ids = [self._ref_to_id(part.strip()) for part in raw.split(",")]
                ids = [i for i in ids if i]
                if ptype == "many2one":
                    return ids[0] if ids else None
                return ids
        except (TypeError, ValueError):
            return None
        return raw

    def _ref_to_id(self, ref):
        if not ref:
            return None
        if ref.isdigit():
            return int(ref)
        record = self.env.ref(ref, raise_if_not_found=False)
        return record.id if record and record._name == self.comodel else None

    # ── Резултатът на формулата ──────────────────────────────────────

    def _poc_coerce(self, value):
        """Привежда резултата на формула към типа на параметъра.

        Вдига ValueError при стойност, която типът не приема; None значи
        „без стойност“.
        """
        self.ensure_one()
        if value is None:
            return None
        ptype = self.param_type
        if ptype == "float":
            value = float(value)
            return round(value, self.digits) if self.digits >= 0 else value
        if ptype == "integer":
            return int(round(float(value)))
        if ptype == "boolean":
            return bool(value)
        if ptype in ("char", "text"):
            return str(value)
        if ptype == "date":
            return fields.Date.to_date(value)
        if ptype == "selection":
            if value not in self.option_ids.mapped("key"):
                raise ValueError(
                    self.env._("%(value)r is not an option of %(code)s")
                    % {"value": value, "code": self.code}
                )
            return value
        if ptype == "tags":
            keys = set(self.option_ids.mapped("key"))
            values = [value] if isinstance(value, str) else list(value)
            unknown = [v for v in values if v not in keys]
            if unknown:
                raise ValueError(
                    self.env._("%(value)r are not options of %(code)s")
                    % {"value": unknown, "code": self.code}
                )
            return values
        if ptype in ("many2one", "many2many"):
            model = self.env[self.comodel]
            if isinstance(value, int):
                value = model.browse(value)
            elif isinstance(value, (list, tuple)):
                value = model.browse(list(value))
            if getattr(value, "_name", None) != self.comodel:
                raise ValueError(
                    self.env._("%(code)s expects %(model)s records")
                    % {"code": self.code, "model": self.comodel}
                )
            return value[:1] if ptype == "many2one" else value
        return value


class SaleOrderPocParamOption(models.Model):
    """Опция на параметър тип Selection или Tags: формулите виждат ключа,
    екранът — етикета."""

    _name = "sale.order.poc.param.option"
    _description = "Production Configuration Parameter Option"
    _order = "sequence, id"

    param_id = fields.Many2one(
        "sale.order.poc.param", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    key = fields.Char(required=True)
    name = fields.Char(string="Label", required=True, translate=True)
    color = fields.Integer(default=0)

    _key_uniq = models.Constraint(
        "unique(param_id, key)", "The option key must be unique per parameter."
    )

    @api.constrains("key")
    def _check_key(self):
        for option in self:
            if not KEY_RE.match(option.key or ""):
                raise ValidationError(
                    self.env._(
                        "The option key %(key)s may contain only lowercase letters, "
                        "digits and underscores.",
                        key=option.key,
                    )
                )
