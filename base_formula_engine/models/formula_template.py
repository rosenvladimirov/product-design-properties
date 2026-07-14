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
from odoo import api, fields, models


class FormulaTemplate(models.Model):
    """Реюзабилен формулен шаблон, независим от домейна.

    Консуматорите (MRP количества, payroll компоненти, ...) реферират
    шаблон или копират формулния текст в свои датирани модели.
    Резолюция по code: company-специфичен запис има приоритет пред
    глобалния (company_id=False) — същата конвенция като
    zen.decision.table.get_active.
    """

    _name = "formula.template"
    _inherit = "formula.engine.mixin"
    _description = "Formula Template"
    _order = "name, id"

    name = fields.Char(required=True)
    code = fields.Char(
        index=True,
        copy=False,
        help="Technical key for programmatic lookup (optional).",
    )
    usage = fields.Char(
        index=True,
        help="Free tag grouping templates per consuming domain "
        "(e.g. 'mrp_bom_qty', 'payroll_component').",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Leave empty for a global template shared by all companies.",
    )
    formula = fields.Text(
        required=True,
        help="Python code executed by the consuming domain. Write the "
        "computed value(s) into output variables (by convention "
        "'result'). The available context variables are defined by "
        "the consumer - check its documentation.",
    )

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "The technical key must be unique per company.",
    )
    # PG третира NULL като distinct → фирменият constraint не пази
    # глобалния скоуп; частичен уникален индекс затваря дупката
    _code_global_uniq = models.UniqueIndex(
        "(code) WHERE company_id IS NULL",
        "The technical key must be unique among global templates.",
    )

    @api.constrains("formula")
    def _constrain_formula(self):
        # Синтактична проверка при запис — изпълнението не валидира повторно
        for template in self:
            template._formula_validate(template.formula)

    @api.model
    def get_by_code(self, code, company=None):
        """Резолвва активен шаблон по code: първо company-специфичния
        запис, после глобалния (company_id=False). Връща празен
        recordset, ако няма нито един.

        Резолюцията е КЪМ МОМЕНТА на извикване (шаблоните не са
        датирани) — за исторически преизчисления консуматорът трябва
        да държи собствени датирани копия на формулния текст (виж
        CONTEXT.md).
        """
        company = company or self.env.company
        # with_company гарантира, че record rule-ът вижда фирмата,
        # дори извикващият да резолвва за фирма извън env.companies
        # (batch/cron по фирми) — иначе тихо пада към глобалния шаблон
        records = self.with_company(company)
        template = records.search(
            [("code", "=", code), ("company_id", "=", company.id)], limit=1
        )
        if not template:
            template = records.search(
                [("code", "=", code), ("company_id", "=", False)], limit=1
            )
        return template

    def evaluate(self, values, outputs=("result",)):
        """Изпълнява формулата на шаблона върху подадения контекст.

        Тънка обвивка над _formula_eval — политиката при грешка и
        съдържанието на контекста остават на извикващия домейн.
        """
        self.ensure_one()
        return self._formula_eval(self.formula, values, outputs=outputs)
