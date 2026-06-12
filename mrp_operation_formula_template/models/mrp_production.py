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


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        res = super().action_confirm()
        self._apply_operation_formulas()
        return res

    def _apply_operation_formulas(self):
        """Прилага операционните формули върху workorder-ите на MO-то:

        - ``skip = True`` → workorder-ът се маха изцяло (суровините му се
          освобождават преди това);
        - ``result``/``duration`` → очаквана продължителност в минути;
        - ``collect_materials = True`` → всички още незакачени raw move-ове
          се консумират в този workorder;
        - ``materials = [продукти]`` → move-овете на тези продукти се
          консумират тук.
        """
        Move = self.env["stock.move"]
        has_wo_field = "workorder_id" in Move._fields
        for production in self:
            for workorder in production.workorder_ids:
                operation = workorder.operation_id
                if not operation or not getattr(
                    operation, "operation_formula", False
                ):
                    continue
                try:
                    result = operation._eval_operation_formula(
                        production,
                        workorder=workorder,
                        default_duration=workorder.duration_expected,
                    )
                except Exception:
                    _logger.warning(
                        "Operation formula of %s failed on MO %s; work "
                        "order left unchanged.",
                        operation.display_name,
                        production.display_name,
                        exc_info=True,
                    )
                    continue
                if not result:
                    continue

                if result.get("skip"):
                    if has_wo_field:
                        production.move_raw_ids.filtered(
                            lambda m, wo=workorder: m.workorder_id == wo
                        ).write({"workorder_id": False})
                    workorder.unlink()
                    continue

                if workorder.duration_expected != result["duration"]:
                    workorder.duration_expected = result["duration"]

                self._apply_formula_employees(workorder, result)

                if not has_wo_field:
                    continue
                if result.get("materials"):
                    product_ids = self._formula_materials_to_ids(
                        result["materials"]
                    )
                    if product_ids:
                        production.move_raw_ids.filtered(
                            lambda m: m.product_id.id in product_ids
                        ).write({"workorder_id": workorder.id})
                elif result.get("collect_materials"):
                    production.move_raw_ids.filtered(
                        lambda m: not m.workorder_id
                    ).write({"workorder_id": workorder.id})

    def _apply_formula_employees(self, workorder, result):
        """Назначава операторите от формулата върху workorder-а.

        Полетата за оператори идват с EE mrp_workorder — пробваме
        кандидатите по ред; на CE изходът се игнорира тихо (debug лог).
        """
        employee_ids = result.get("employees")
        if not employee_ids:
            return
        for field in ("employee_assigned_ids", "employee_ids"):
            if field in workorder._fields:
                workorder.write({field: [(6, 0, list(employee_ids))]})
                return
        _logger.debug(
            "Operation formula set employees, but %s has no operator "
            "field (CE without mrp_workorder) — ignored.",
            workorder._name,
        )

    @staticmethod
    def _formula_materials_to_ids(materials):
        """Списък от продукти (recordset-и или единични) → set от id-та."""
        ids = set()
        for item in materials if isinstance(materials, (list, tuple)) else [materials]:
            if hasattr(item, "ids"):
                ids.update(item.ids)
            elif isinstance(item, int):
                ids.add(item)
        return ids
