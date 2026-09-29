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
"""Цената на офертата от матрицата (ADR sale-order-poc/0019).

На черновата партида НЕ се ражда — смята се само колко ще струва изделието,
а цената отива в POC и в реда. Веригата: матрицата разгъва рецептата на
сухо по контекста от POC, стандартният двигател на Odoo цени рецептата, а
машината за референтна цена превръща себестойността в цена.
"""

from odoo import Command, fields, models
from odoo.tools import float_compare

from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    matrix_cost_unit = fields.Float(
        string="Matrix Unit Cost",
        digits="Product Price",
        readonly=True,
        copy=False,
        groups="mrp_design_matrix_cost.group_design_manager",
        help="Cost of one unit of this configuration: the bill of materials "
        "the matrix builds for it, priced by the standard costing.",
    )
    matrix_price_unit = fields.Float(
        string="Matrix Unit Price",
        digits="Product Price",
        readonly=True,
        copy=False,
        help="Reference price of this configuration: the matrix builds its "
        "bill of materials without producing anything, the standard costing "
        "prices it and the reference pricelist turns the cost into a price. "
        "While the quotation is a draft or sent, it becomes the price of the "
        "line.",
    )
    matrix_price_note = fields.Char(
        string="Matrix Price Note",
        readonly=True,
        copy=False,
        help="Why the matrix gave no price, or what its constraints warn "
        "about for this configuration.",
    )
    # последно вписаната цена в реда: разминаване значи ръчна цена
    matrix_price_written = fields.Float(
        digits="Product Price", readonly=True, copy=False
    )

    def _poc_compute_derived(self):
        res = super()._poc_compute_derived()
        self._poc_matrix_price()
        return res

    def _poc_matrix_price(self):
        """Колко ще струва конфигурацията; цената отива в POC и в реда.

        Само докато офертата е чернова или изпратена. Смята се в основната
        мярка на артикула, за цялото количество на реда: пускането и
        постоянният брак се разпределят върху поръчката, не върху един брой.
        В реда цената отива в неговата мярка (кашон, пакет…).

        Цена на реда, сменена на ръка, не се презаписва — разпознава се по
        разминаване с последно вписаната.
        """
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for poc in self:
            line = poc.sudo().sale_line_id
            if not line or line.order_id.state not in ("draft", "sent"):
                continue
            context = poc._poc_matrix_context()
            if context is None:
                continue
            product = line.product_id
            qty = (
                line.product_uom_id._compute_quantity(
                    line.product_uom_qty or 1.0, product.uom_id
                )
                or 1.0
            )
            cost, note, warnings = poc._poc_matrix_dry_run_cost(product, context, qty)
            price = 0.0
            if not note:
                price, note = poc._poc_matrix_reference_price(product, cost, qty)
            # защо няма цена — първо; предупрежденията на T0 — след него
            note = "\n".join([text for text in [note, *warnings] if text])
            line_price = product.uom_id._compute_price(price, line.product_uom_id)
            system = poc.with_context(poc_system=True).sudo()
            system.write(
                {
                    "matrix_cost_unit": cost,
                    "matrix_price_unit": line_price,
                    "matrix_price_note": note or False,
                }
            )
            if not line_price:
                continue
            written = poc.matrix_price_written
            if written and float_compare(
                line.price_unit, written, precision_digits=precision
            ):
                continue
            line.price_unit = line_price
            system.matrix_price_written = line_price

    def _poc_matrix_dry_run_cost(self, product, context, qty):
        """Себестойност за брой: матрицата на сухо, рецептата — по Odoo.

        Матрицата пуска таблиците и формулите без запис и връща редовете и
        операциите за това количество. От тях се сглобява рецепта, която
        НЕ се записва, и я цени стандартният двигател (`_compute_bom_price`
        — същият като „Изчисли цената от рецептата“ на артикула).

        Връща (себестойност, бележка, предупреждения); бележка значи „няма
        цена“, а предупрежденията на T0 не я спират.
        """
        self.ensure_one()
        Bom = self.env["mrp.bom"].sudo()
        bom = Bom._bom_find(product).get(product)
        if not bom:
            return (
                0.0,
                self.env._("No bill of materials for %s.", product.display_name),
                [],
            )
        # ограниченията (T0) — същите, които спират производствената поръчка;
        # предупреждението не спира цената, но търговецът го вижда
        errors, warnings = self._poc_matrix_constraints(bom, context, qty)
        if errors:
            return 0.0, "\n".join(errors), warnings
        # sudo минава проверката за достъп до парите — пише се само цената
        dry = bom.simulate_design_cost(context, qty)
        if dry.get("error"):
            return 0.0, dry["error"], warnings
        if dry.get("incomplete"):
            return 0.0, self.env._("The matrix calculation is incomplete."), warnings
        lines = [
            Command.create(
                {
                    "product_id": row["product_id"],
                    "product_qty": row["qty"],
                    "product_uom_id": row.get("uom_id")
                    or self.env["product.product"].browse(row["product_id"]).uom_id.id,
                }
            )
            for row in dry.get("lines") or []
            if row.get("product_id") and row.get("qty")
        ]
        operations = [
            Command.create(
                {
                    "name": op["name"],
                    "workcenter_id": op["workcenter_id"],
                    "time_mode": "manual",
                    "time_cycle_manual": op["minutes"],
                }
            )
            for op in dry.get("operations") or []
            if op.get("workcenter_id") and op.get("minutes")
        ]
        virtual = Bom.new(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_qty": qty,
                "product_uom_id": product.uom_id.id,
                "type": "normal",
                "bom_line_ids": lines,
                "operation_ids": operations,
            }
        )
        return product.sudo()._compute_bom_price(virtual), False, warnings

    def _poc_matrix_constraints(self, bom, context, qty):
        """T0 на рецептата за тази конфигурация: (грешки, предупреждения).

        Същото като при създаване на производствената поръчка (грешка я
        спира, предупреждението отива в чатъра ѝ), но тук само се чете.
        Текстовете са на езика на потребителя, през речника на слоя, който
        ги е дал. Грешка в самата таблица е грешка: цена по счупени
        ограничения не се дава.
        """
        self.ensure_one()
        if not bom.constraint_table:
            return [], []
        ctx = dict(context)
        ctx.setdefault("qty", qty)
        try:
            t0 = ZenWrapper.evaluate(bom.constraint_table, ctx)
        except Exception as exc:  # noqa: BLE001 — таблицата е данни
            return [self.env._("The matrix constraints failed: %s", exc)], []
        rows = t0 if isinstance(t0, list) else [t0] if isinstance(t0, dict) else []
        errors, warnings = [], []
        for row in rows:
            if not isinstance(row, dict):
                continue
            level = row.get("level")
            if level not in ("error", "warning"):
                continue
            message = bom._translate_rule_message(row.get("message", ""))
            (errors if level == "error" else warnings).append(message)
        return errors, warnings

    def _poc_matrix_reference_price(self, product, cost, qty):
        """Себестойността през машината за референтна цена.

        Същата машина като картона на артикула и дневния крон — с
        подадената себестойност, без да се пише в артикула. Меко засичане:
        машината е OPL-1 и този AGPL модул не зависи от нея.
        """
        self.ensure_one()
        if not hasattr(product, "_reference_price_check"):
            return 0.0, self.env._("The reference price engine is not installed.")
        company = self.env.company
        data = (
            product.sudo()
            .with_company(company)
            .with_context(reference_price_costs={product.id: cost})
            ._reference_price_check(
                company,
                fields.Datetime.now(),
                qty,
                company.reference_price_tolerance,
            )
            .get(product.id)
            or {}
        )
        if not data.get("reference"):
            states = dict(
                product._fields["reference_price_state"]._description_selection(
                    self.env
                )
            )
            state = data.get("state")
            return 0.0, self.env._(
                "No reference price: %s", states.get(state, state or "?")
            )
        return data["reference"], False
