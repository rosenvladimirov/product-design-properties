# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
import ast
import builtins
import re

from odoo import Command, models
from odoo.exceptions import UserError

# базовите ключове на PDP и изходите на формулата
ENGINE_NAMES = frozenset(
    {
        "bom_line",
        "operation",
        "product",
        "product_uom",
        "product_uom_qty",
        "production",
        "quantity",
        "env",
        "design_context",
        "result",
        "skip",
        "uom",
        "add_products",
    }
)


# формулата, която генераторът слага на реда на кит; по нея се познава
KIT_FORMULA = "skip = not %s"


def free_names(formula):
    """Имената, които формулата ЧЕТЕ, без своите временни променливи."""
    try:
        tree = ast.parse(formula or "", mode="exec")
    except SyntaxError:
        return set()
    loads, stores = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (loads if isinstance(node.ctx, ast.Load) else stores).add(node.id)
        elif isinstance(node, ast.comprehension):
            for target in ast.walk(node.target):
                if isinstance(target, ast.Name):
                    stores.add(target.id)
    return loads - stores


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def action_check_poc_formulas(self):
        """Единствената защита срещу сгрешено име във формула.

        Грешка във формула НЕ спира производството: PDP дава стандартното
        количество и предупреждение в лога (ADR sale-order-poc/0006).
        Затова имената се проверяват тук, преди формулата да стигне до
        поръчка.
        """
        unknown = []
        for bom in self:
            template = bom.product_tmpl_id.poc_template_id
            if not template:
                raise UserError(
                    self.env._(
                        "%(product)s has no production configuration template.",
                        product=bom.product_tmpl_id.display_name,
                    )
                )
            codes = set(
                (
                    template.line_ids
                    | template.allowed_aspect_ids.line_ids
                ).param_id.mapped("code")
            )
            allowed = (
                codes
                | ENGINE_NAMES
                | self.env["mrp.production"]._poc_context_names()
                | set(dir(builtins))
            )
            for line in bom.bom_line_ids.filtered("quantity_formula"):
                missing = sorted(free_names(line.quantity_formula) - allowed)
                if missing:
                    unknown.append(
                        "%s: %s" % (line.product_id.display_name, ", ".join(missing))
                    )
        if unknown:
            raise UserError(
                self.env._(
                    "These names are not in the configuration:\n%(lines)s",
                    lines="\n".join(unknown),
                )
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._(
                    "Every formula name is in the production configuration."
                ),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    # ── Опциите на китовете (ADR sale-order-poc/0023) ────────────────

    def _poc_kit_option_lines(self):
        """Редовете с фантомен кит, които са ОПЦИЯ в конфигурацията.

        Кука за слоя на фирмата. Базата: всеки фантомен кит, освен ако
        китът сам казва, че е общ (``pcb_kit_option == "Common"`` на кита,
        ако такова поле има — без зависимост от модула, който го носи).
        """
        self.ensure_one()
        lines = self.bom_line_ids.filtered(
            lambda l: l.child_bom_id.type == "phantom"
        )
        if "pcb_kit_option" in self.env["mrp.bom"]._fields:
            lines = lines.filtered(
                lambda l: (l.child_bom_id.pcb_kit_option or "Common") != "Common"
            )
        return lines

    def _poc_kit_option_default(self, line):
        """Отметнат ли е китът в нова конфигурация. Кука за слоя на фирмата;
        базата чете ``pcb_kit_default_on`` на кита, ако такова поле има."""
        kit = line.child_bom_id
        return bool("pcb_kit_default_on" in kit._fields and kit.pcb_kit_default_on)

    def _poc_kit_option_code(self, line):
        """Кодът на отметката: ``kit_`` + вътрешната референция на кита.

        ``#`` в референцията означава ДРУГ кит (``Piezo_PIC#`` до
        ``Piezo_PIC``), затова не се трие, а става ``_alt``; префиксът
        ``KIT-`` на китовете от импорта пада. Кодът е зает от отметка на
        друг кит (сблъсък след изчистването) — добавя се id на продукта.
        """
        product = line.product_id
        ref = (product.default_code or "").lower().replace("#", "_alt")
        ref = re.sub(r"^kit[-_]", "", ref)
        base = re.sub(r"[^a-z0-9]+", "_", ref).strip("_") or str(product.id)
        code = "kit_%s" % base
        taken = (
            self.env["sale.order.poc.param"]
            .sudo()
            .with_context(active_test=False)
            .search([("code", "=", code)], limit=1)
        )
        if taken and taken.name != product.display_name:
            code = "%s_%s" % (code, product.id)
        return code

    def action_poc_kit_options(self):
        """По една отметка в конфигурацията за всеки опционен кит.

        За всеки ред от ``_poc_kit_option_lines``: речникът получава
        отметка (по кода, ако я има — само се дописва), шаблонът на
        продукта — ред с нея, а редът на BoM — формулата
        ``skip = not <код>``. Шаблон, ако продуктът няма, се създава.
        Може да се пуска пак: нищо не се дублира, а ред с ЧУЖДА формула не
        се пипа и се изброява в отговора.
        """
        Param = self.env["sale.order.poc.param"].sudo()
        Template = self.env["sale.order.poc.template"].sudo()
        Formula = self.env["mrp.bom.line.formula.template"].sudo()
        done, foreign = [], []
        for bom in self:
            lines = bom._poc_kit_option_lines()
            if not lines:
                raise UserError(
                    self.env._(
                        "%(bom)s has no optional phantom kits.",
                        bom=bom.display_name,
                    )
                )
            product_tmpl = bom.product_tmpl_id
            template = product_tmpl.poc_template_id
            if not template:
                template = Template.create(
                    {
                        "name": product_tmpl.name,
                        "code": "kits_%s" % product_tmpl.id,
                    }
                )
                product_tmpl.sudo().poc_template_id = template
            for line in lines:
                code = bom._poc_kit_option_code(line)
                formula = KIT_FORMULA % code
                current = line.quantity_formula or ""
                if current and current.strip() != formula:
                    foreign.append(line.product_id.display_name)
                    continue
                param = Param.with_context(active_test=False).search(
                    [("code", "=", code)], limit=1
                )
                default = "1" if bom._poc_kit_option_default(line) else "0"
                if not param:
                    param = Param.create(
                        {
                            "code": code,
                            "name": line.product_id.display_name,
                            "param_type": "boolean",
                            "default_value": default,
                        }
                    )
                elif param.param_type != "boolean":
                    foreign.append(line.product_id.display_name)
                    continue
                else:
                    param.write({"active": True, "default_value": default})
                if param not in template.line_ids.param_id:
                    template.line_ids = [Command.create({"param_id": param.id})]
                if not current:
                    line.formula_template_id = Formula.search(
                        [("quantity_formula", "=", formula)], limit=1
                    ) or Formula.create(
                        {
                            "name": "Kit option %s" % code,
                            "quantity_formula": formula,
                        }
                    )
                done.append(code)
        message = self.env._(
            "%(count)s kit options are in the configuration.", count=len(done)
        )
        if foreign:
            message += "\n" + self.env._(
                "Not touched, they have another formula: %(kits)s",
                kits=", ".join(foreign),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if foreign else "success",
                "message": message,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
