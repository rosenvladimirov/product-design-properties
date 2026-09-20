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
import math
from collections import defaultdict

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    """Производствената поръчка чете POC на живо (ADR sale-order-poc/0009).

    Мостът няма собствен формулен двигател: количествата идват от
    експлозията, каквато и да е тя (ядрото или Stage 2 от
    sale_order_poc_mrp_formula). Мостът само я пуска отново и пише
    разликите (ADR sale-order-poc/0008).
    """

    _inherit = "mrp.production"

    poc_id = fields.Many2one(
        "sale.order.poc",
        string="Production Configuration",
        index="btree_not_null",
        readonly=True,
        copy=True,
        tracking=True,
    )
    # схемата иска път с точно една точка (ORM/fields_properties.py:96)
    poc_template_id = fields.Many2one(related="poc_id.template_id", store=True)
    poc_params = fields.Properties(
        string="Configuration",
        related="poc_id.params",
        definition="poc_template_id.param_definition",
        readonly=True,
    )
    poc_summary = fields.Char(related="poc_id.summary", string="Configuration Summary")

    # ── Договорът на Stage 2 ─────────────────────────────────────────

    def _poc_formula_context(self):
        """Договорът за формулите на редовете от BoM (ADR sale-order-poc/0005).

        Стойностите на POC по кодовете им плюс производственият контекст.
        Без нито един базов ключ на PDP: имената тук са запазени в речника
        (sale_order_poc POC_RESERVED_NAMES), затова параметър не може да ги
        засенчи.
        """
        self.ensure_one()
        poc = self.poc_id
        if not poc:
            return {}
        return {
            **poc._poc_values(),
            "poc": poc,
            "poc_product": poc.product_id,
            "lot": self.lot_producing_ids[:1] or poc.lot_id,
            "order_qty": poc.product_uom_qty,
            "order_uom": poc.product_uom_id,
            "mo_qty": self.product_qty,
            "mo_uom": self.product_uom_id,
            "mo_product": self.product_id,
            "ceil": math.ceil,
            "floor": math.floor,
            "sqrt": math.sqrt,
            "pi": math.pi,
        }

    @api.model
    def _poc_context_names(self):
        """Имената на договора без стойностите на POC — един източник и за
        проверката на формулите (sale_order_poc_mrp_formula)."""
        return frozenset(
            {
                "poc",
                "poc_product",
                "lot",
                "order_qty",
                "order_uom",
                "mo_qty",
                "mo_uom",
                "mo_product",
                "ceil",
                "floor",
                "sqrt",
                "pi",
            }
        )

    def _get_move_raw_values(
        self, product, product_uom_qty, product_uom, operation_id=False, bom_line=False
    ):
        vals = super()._get_move_raw_values(
            product, product_uom_qty, product_uom, operation_id, bom_line
        )
        if self.poc_id:
            # суровината носи POC: процюърмънтът ѝ ражда под-MO на същия POC
            vals["poc_id"] = self.poc_id.id
        return vals

    # ── Лотът ────────────────────────────────────────────────────────

    def action_generate_serial(self, workorder=False):
        self.ensure_one()
        if self.poc_id and self.product_tracking == "lot" and not self.lot_producing_ids:
            # лотът на POC, не нов от поредността (ADR sale-order-poc/0007)
            lot = self.poc_id.sudo()._poc_lot(self.product_id)
            self.lot_producing_ids = [Command.set(lot.ids)]
            return True
        return super().action_generate_serial(workorder=workorder)

    def _prepare_stock_lot_values(self):
        vals = super()._prepare_stock_lot_values()
        if self.poc_id and self.product_tracking == "serial":
            # серийният номер влиза в семейството; номерът на партидата е
            # поредният, защото (poc, продукт, партида) е уникално
            last = (
                self.env["stock.lot"]
                .sudo()
                .search(
                    [
                        ("poc_id", "=", self.poc_id.id),
                        ("product_id", "=", self.product_id.id),
                    ],
                    order="poc_batch desc",
                    limit=1,
                )
            )
            vals.update(
                poc_id=self.poc_id.id,
                poc_batch=(last.poc_batch or 0) + 1,
                ref=self.poc_id.name,
            )
        return vals

    def _get_backorder_mo_vals(self):
        vals = super()._get_backorder_mo_vals()
        if self.poc_id and self.product_tracking == "lot" and self.lot_producing_ids:
            # ядрото чисти лота на бекордера; той остава на POC — същият или,
            # по флага на шаблона, следващата партида (ADR sale-order-poc/0007)
            if self.poc_id.template_id.lot_batches:
                lot = self.poc_id.sudo()._poc_lot(self.product_id, new_batch=True)
            else:
                lot = self.lot_producing_ids
            vals["lot_producing_ids"] = [Command.set(lot.ids)]
        return vals

    def _split_productions(
        self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False
    ):
        productions = super()._split_productions(
            amounts=amounts,
            cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty,
        )
        # ядрото мести редовете на готовия продукт в бекордера СЛЕД като той е
        # създаден, със стария лот — партидата n+1 остава само на хартия
        for production in productions.filtered(
            lambda p: p.poc_id and p.product_tracking == "lot" and p.lot_producing_ids
        ):
            production.move_finished_ids.filtered(
                lambda m: m.product_id == production.product_id
                and m.state not in ("done", "cancel")
            ).move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.lot_id != production.lot_producing_ids
            ).lot_id = production.lot_producing_ids
        return productions

    # ── Сливане ──────────────────────────────────────────────────────

    def _pre_action_split_merge_hook(self, merge=False, split=False):
        if merge and len(self) > 1 and (
            len(self.poc_id) > 1 or (self.poc_id and not all(self.mapped("poc_id")))
        ):
            raise UserError(
                self.env._(
                    "Only manufacturing orders of the same production configuration "
                    "can be merged."
                )
            )
        return super()._pre_action_split_merge_hook(merge=merge, split=split)

    def action_merge(self):
        poc = self.poc_id
        res = super().action_merge()
        if poc and isinstance(res, dict) and res.get("res_id"):
            # ядрото ражда новото MO с изричен списък стойности без POC
            merged = self.browse(res["res_id"])
            vals = {"poc_id": poc.id}
            if merged.product_tracking == "lot":
                lot = poc.sudo()._poc_lot(merged.product_id)
                vals["lot_producing_ids"] = [Command.set(lot.ids)]
            merged.write(vals)
            merged._poc_refresh()
        return res

    # ── Преизчисляване по POC ────────────────────────────────────────

    def _poc_unstarted(self):
        """Потвърдено и нищо не е тръгнало: нито работна поръчка, нито
        взета или изписана суровина (ADR sale-order-poc/0008)."""
        self.ensure_one()
        return (
            self.state == "confirmed"
            and not self.workorder_ids.filtered(
                lambda wo: wo.state in ("progress", "done")
            )
            and not self.move_raw_ids.filtered(
                lambda move: move.picked or move.state == "done"
            )
        )

    def _poc_refresh(self):
        """Входната точка след промяна на POC, количеството или BoM.

        Чернова — компютът на суровините; потвърдено незапочнато — нова
        експлозия и разликите; започнато — activity за плановика и бутон.
        """
        for production in self.filtered("poc_id"):
            if production.state == "draft":
                production._compute_move_raw_ids()
            elif production._poc_unstarted():
                production._poc_apply_explosion()
            elif production.state in ("confirmed", "progress", "to_close"):
                production._poc_schedule_recompute()

    def action_poc_recompute(self):
        """Бутонът „Recompute from Configuration“ — и за започнато MO."""
        for production in self.filtered("poc_id"):
            if production.state == "draft":
                production._compute_move_raw_ids()
            elif production.state in ("confirmed", "progress", "to_close"):
                production._poc_apply_explosion()
                production.activity_ids.filtered(
                    lambda a: a.summary == production._poc_activity_summary()
                ).action_done()
        return True

    def _poc_activity_summary(self):
        return self.env._("Recompute from Configuration")

    def _poc_schedule_recompute(self, note=None):
        self.ensure_one()
        summary = self._poc_activity_summary()
        if self.activity_ids.filtered(lambda a: a.summary == summary):
            return
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=summary,
            note=note
            or self.env._(
                "The production configuration %(poc)s changed after this order "
                "started. Check the components and recompute them from the "
                "configuration.",
                poc=self.poc_id.display_name,
            ),
            user_id=self.user_id.id or self.env.uid,
        )

    def _poc_upstream_productions(self):
        """Под-MO на същия POC, които захранват суровините на това MO — по
        веригата move_orig_ids, и при pbm (подаването е между тях)."""
        self.ensure_one()
        Move = self.env["stock.move"]
        productions = self.env["mrp.production"]
        seen = Move
        moves = self.move_raw_ids.move_orig_ids
        while moves:
            moves -= seen
            seen |= moves
            productions |= moves.production_id
            moves = moves.filtered(lambda m: not m.production_id).move_orig_ids
        return productions.filtered(
            lambda p: p.poc_id == self.poc_id and p.state not in ("done", "cancel")
        )

    def _poc_sync_upstream(self):
        """Под-MO следва нуждата на родителя и нагоре, и надолу (ADR
        sale-order-poc/0016). Ядрото само увеличава под-MO, а при намаление го
        оставя голямо, без сигнал. Нуждата е сборът от движенията, които
        под-MO захранва; незапочнато — ново количество, започнато — activity.
        """
        self.ensure_one()
        for sub in self._poc_upstream_productions():
            finished = sub.move_finished_ids.filtered(
                lambda m, sub=sub: m.product_id == sub.product_id
                and m.state not in ("done", "cancel")
            )
            need = sum(
                dest.product_uom._compute_quantity(
                    dest.product_uom_qty, sub.product_uom_id
                )
                for dest in finished.move_dest_ids
                if dest.state != "cancel"
            )
            uom = sub.product_uom_id
            if uom.compare(need, sub.product_qty) == 0:
                continue
            if uom.compare(need, 0.0) > 0 and (
                sub.state == "draft" or sub._poc_unstarted()
            ):
                self.env["change.production.qty"].sudo().with_context(
                    skip_activity=True
                ).create({"mo_id": sub.id, "product_qty": need}).change_prod_qty()
            else:
                sub._poc_schedule_recompute(
                    note=self.env._(
                        "%(parent)s now needs %(need)s %(uom)s of %(product)s "
                        "for configuration %(poc)s; this order makes %(qty)s.",
                        parent=self.name,
                        need=need,
                        uom=uom.name,
                        product=sub.product_id.display_name,
                        poc=sub.poc_id.display_name,
                        qty=sub.product_qty,
                    )
                )

    def _poc_apply_explosion(self):
        """Нова експлозия срещу суровините на потвърденото MO.

        Съпоставката е по (ред на BoM, продукт): един ред може да даде
        няколко движения (add_products). Пишат се само разликите; движение
        без съответствие отива на 0, без да се трие (CORE
        stock/models/stock_move.py:2339-2341); ново се създава и
        потвърждава. Никога под вече взетото. Разликата отива в чатъра.
        """
        self.ensure_one()
        Move = self.env["stock.move"]
        moves = self.move_raw_ids.filtered(
            lambda m: m.bom_line_id and m.state not in ("done", "cancel")
        )
        existing = defaultdict(lambda: Move)
        for move in moves:
            existing[(move.bom_line_id.id, move.product_id.id)] |= move
        wanted = {}
        for vals in self._get_moves_raw_values():
            key = (vals["bom_line_id"], vals["product_id"])
            if key in wanted:
                uom = self.env["uom.uom"].browse(vals["product_uom"])
                first_uom = self.env["uom.uom"].browse(wanted[key]["product_uom"])
                wanted[key]["product_uom_qty"] += uom._compute_quantity(
                    vals["product_uom_qty"], first_uom
                )
            else:
                wanted[key] = dict(vals)
        changes = []
        below = []
        to_create = []
        for key, vals in wanted.items():
            key_moves = existing.pop(key, Move)
            if not key_moves:
                to_create.append(vals)
                changes.append((vals["product_id"], 0.0, vals["product_uom_qty"]))
                continue
            move, rest = key_moves[:1], key_moves[1:]
            new_qty = (
                self.env["uom.uom"]
                .browse(vals["product_uom"])
                ._compute_quantity(vals["product_uom_qty"], move.product_uom)
            )
            self._poc_set_move_qty(move, new_qty, changes, below)
            for extra in rest:
                self._poc_set_move_qty(extra, 0.0, changes, below)
        for key_moves in existing.values():
            for move in key_moves:
                self._poc_set_move_qty(move, 0.0, changes, below)
        if below:
            raise UserError(
                self.env._(
                    "%(mo)s: the configuration needs less than already consumed:\n%(moves)s",
                    mo=self.name,
                    moves="\n".join(below),
                )
            )
        if to_create:
            Move.create(to_create)._action_confirm()
        self._poc_post_explosion(changes)
        if changes:
            self._poc_sync_upstream()

    def _poc_set_move_qty(self, move, new_qty, changes, below):
        rounding = move.product_uom
        if rounding.compare(new_qty, move.product_uom_qty) == 0:
            return
        consumed = move.quantity if move.picked else 0.0
        if rounding.compare(new_qty, consumed) < 0:
            below.append(
                "%s: %s < %s"
                % (move.product_id.display_name, new_qty, consumed)
            )
            return
        changes.append((move.product_id.id, move.product_uom_qty, new_qty))
        move.product_uom_qty = new_qty

    def _poc_post_explosion(self, changes):
        if not changes:
            return
        products = self.env["product.product"].browse([c[0] for c in changes])
        names = {p.id: p.display_name for p in products}
        self.message_post(
            body=Markup("<p>%s</p><ul>%s</ul>")
            % (
                self.env._("Components recomputed from the configuration:"),
                Markup().join(
                    Markup("<li>%s: %s → %s</li>") % (names[pid], old, new)
                    for pid, old, new in changes
                ),
            )
        )

    def _link_bom(self, bom):
        res = super()._link_bom(bom)
        # Update BoM на потвърдено MO: ядрото връща статичните количества
        self._poc_refresh()
        return res
