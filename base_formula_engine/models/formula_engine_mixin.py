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
from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval, test_python_expr

DEFAULT_OUTPUTS = ("result",)


class FormulaEngineMixin(models.AbstractModel):
    """Генерично формулно ядро: валидация + safe_eval изпълнение.

    Domain-agnostic извлечение на evaluation механиката, чийто
    произход е формулният път на mrp_bom_line_formula_template
    (bom_line._eval_quantity_formula). Ядрото НЕ познава домейна:
    извикващият строи контекста и обявява изходите, които го
    интересуват.

    Политика при грешка НЯМА: изключенията от формулата се
    разпространяват. Домейнът решава какво прави — MRP пада назад към
    стандартното количество (с warning), заплатите гърмят твърдо
    (грешен фиш никога не минава тихо).
    """

    _name = "formula.engine.mixin"
    _description = "Formula Engine Mixin"

    # ── Валидация ────────────────────────────────────────────────────

    @api.model
    def _formula_check(self, formula):
        """Синтактична проверка (exec режим).

        Връща съобщението за грешка или False при валидна формула —
        удобно за @api.constrains върху формулни полета в консуматорите.
        """
        if not formula:
            return False
        try:
            return test_python_expr(expr=formula, mode="exec")
        except NameError as exc:
            # core test_python_expr хваща само Syntax/Type/ValueError;
            # забранено име (dunder, напр. net__total) вдига NameError —
            # връщаме го като съобщение, за да не пропагира гол traceback
            return str(exc)

    @api.model
    def _formula_validate(self, formula):
        """Валидира формула; вдига ValidationError при синтактична грешка."""
        error_message = self._formula_check(formula)
        if error_message:
            raise ValidationError(error_message)

    # ── Изпълнение ───────────────────────────────────────────────────

    @api.model
    def _formula_eval(self, formula, values, outputs=DEFAULT_OUTPUTS, strict=False):
        """Изпълнява формула (exec) върху контекст и връща обявените изходи.

        ``formula``
            Python код; пише резултатите си като променливи в контекста
            (например ``result = base * rate``).
        ``values``
            Контекстът (dict). Извикващият решава какво влиза в него —
            включително дали да инжектира ``env`` (виж CONTEXT.md за
            границата на доверие). Odoo 19+ safe_eval го мутира
            in-place, така че след изпълнението извикващият вижда и
            необявените променливи, ако му трябват.
        ``outputs``
            Имена на изходни променливи. Връща се dict с наличните
            след изпълнението.
        ``strict``
            False (по подразбиране): изход, който вече е бил в
            контекста, се брои за наличен — това позволява seed-нат
            default (MRP паттернът: ``quantity`` = стандартното
            количество), но при ПРЕИЗПОЛЗВАН контекст извикващият е
            длъжен да чисти изходните ключове между изпълненията,
            иначе ще прочете stale стойност от предишната формула.
            True (payroll паттернът): обявените изходи се МАХАТ от
            контекста преди изпълнението — връщат се само реално
            присвоени от формулата стойности, а липсващ изход вдига
            ValueError (твърд fail, нищо не минава тихо).

        Синтаксисът НЕ се валидира повторно при изпълнение (формулните
        полета се валидират при запис през ``_formula_check``);
        синтактична грешка би се проявила като изключение от safe_eval.
        """
        extra = self._formula_eval_context(values)
        if extra is not values and extra:
            # hook-ът е върнал нов/допълнителен dict — сливаме обратно,
            # за да остане валиден in-place контрактът върху values
            values.update(extra)
        if strict:
            for name in outputs:
                values.pop(name, None)
        safe_eval(formula, values, mode="exec")
        result = {name: values[name] for name in outputs if name in values}
        if strict and len(result) != len(outputs):
            missing = [name for name in outputs if name not in result]
            raise ValueError(
                "Formula did not assign required output(s): %s"
                % ", ".join(missing)
            )
        return result

    @api.model
    def _formula_eval_context(self, values):
        """Extension hook: разширенията добавят свои символи към
        контекста (аналог на design_context инжекцията в MRP пътя).

        Контракт: или мутирай подадения dict и върни СЪЩИЯ обект, или
        върни dict с ДОПЪЛНИТЕЛНИ символи — kernel-ът ги слива обратно
        във values (in-place контрактът към извикващия се пази и в
        двата случая). Базата връща контекста непроменен."""
        return values
