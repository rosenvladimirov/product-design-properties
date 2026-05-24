import logging

from odoo import models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Exception classes referenced by `except Exception:` clauses inside BoM
# formulas — safe_eval's builtin allowlist excludes them by default.
_FORMULA_EXCEPTIONS = {
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "ZeroDivisionError": ZeroDivisionError,
    "KeyError": KeyError,
    "AttributeError": AttributeError,
}


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    def _evaluate_quantity(self, params):
        """Evaluate this BoM line's quantity given a parameter namespace.

        Formulas typically wrap the body in ``try/except Exception:`` — that's
        a Python *statement*, so we must run safe_eval in ``mode='exec'`` and
        read the resulting ``quantity`` name out of the namespace.  Exception
        classes referenced by the except clause are injected (safe_eval's
        default builtin allowlist excludes them).

        Falls back to ``product_qty`` if no formula or eval fails.
        """
        self.ensure_one()
        formula = (self.quantity_formula or "").strip()
        if not formula:
            return self.product_qty
        try:
            ns = dict(params or {})
            ns.update(_FORMULA_EXCEPTIONS)
            safe_eval(formula, globals_dict=ns, mode="exec", nocopy=True)
            value = ns.get("quantity", ns.get("result", self.product_qty))
            return float(value)
        except Exception as e:
            _logger.warning(
                "[sale_design_pricing] Formula eval failed on bom.line %s (%s): %s",
                self.id, formula, e,
            )
            return self.product_qty
