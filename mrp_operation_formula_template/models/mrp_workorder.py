# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def _get_duration_expected(self, alternative_workcenter=False, ratio=1):
        """Формулата на операцията може да замени стандартната
        очаквана продължителност (в минути)."""
        duration = super()._get_duration_expected(
            alternative_workcenter=alternative_workcenter, ratio=ratio
        )
        operation = self.operation_id
        if not operation or not getattr(operation, "operation_formula", False):
            return duration
        try:
            result = operation._eval_operation_formula(
                self.production_id,
                workorder=self,
                default_duration=duration,
            )
        except Exception:
            _logger.warning(
                "Operation formula of %s failed; keeping the standard "
                "expected duration.",
                operation.display_name,
                exc_info=True,
            )
            return duration
        if not result or result.get("skip"):
            # skip се прилага при потвърждаване (mrp_production);
            # тук просто оставяме стандартната стойност
            return duration
        return result["duration"]
