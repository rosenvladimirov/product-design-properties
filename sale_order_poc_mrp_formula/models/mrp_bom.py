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

from odoo import models
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
