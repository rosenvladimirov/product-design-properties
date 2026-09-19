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
from odoo.exceptions import UserError
from odoo.tools import float_compare


class StockMove(models.Model):
    """Движенията носят конфигурацията като ``sale_line_id``.

    Ограниченото движение (``poc_lot_restrict``) резервира само от
    семейството лотове на своя POC — (poc_id, product_id), подредени по
    партида. Единичният лот е семейство от един. Структурата е като OCA
    stock_restrict_lot, но ключът е семейството, не един лот, затова
    партидите (ADR sale-order-poc/0007) не искат заобикаляне на чужд модул.
    """

    _inherit = "stock.move"

    poc_id = fields.Many2one(
        "sale.order.poc",
        string="Production Configuration",
        index="btree_not_null",
        readonly=True,
    )
    poc_lot_restrict = fields.Boolean(
        string="Configuration Lots Only",
        readonly=True,
        help="The move takes only lots of its production configuration.",
    )

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        if self.poc_id:
            values["poc_id"] = self.poc_id.id
            values["poc_lot_restrict"] = self.poc_lot_restrict
        return values

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        # движения на различни конфигурации не се сливат в едно
        return super()._prepare_merge_moves_distinct_fields() + ["poc_id"]

    # ── Семейството лотове ───────────────────────────────────────────

    def _poc_restricted(self):
        """Ограничението важи за движения, които вземат от склада.

        Входящо от доставчик или от производството няма какво да резервира;
        там лотът идва с движението и не бива да се отказва.
        """
        self.ensure_one()
        return bool(
            self.poc_lot_restrict
            and self.poc_id
            and self.product_id.tracking != "none"
            and self.location_id.usage in ("internal", "transit")
        )

    def _poc_family_lots(self):
        self.ensure_one()
        return self.env["stock.lot"].search(
            [
                ("poc_id", "=", self.poc_id.id),
                ("product_id", "=", self.product_id.id),
            ],
            order="poc_batch, id",
        )

    def _get_available_quantity(
        self,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
        allow_negative=False,
    ):
        self.ensure_one()
        if (
            lot_id
            or not self._poc_restricted()
            or location_id.should_bypass_reservation()
        ):
            return super()._get_available_quantity(
                location_id,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                allow_negative=allow_negative,
            )
        return sum(
            super(StockMove, self)._get_available_quantity(
                location_id,
                lot_id=lot,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
                allow_negative=allow_negative,
            )
            for lot in self._poc_family_lots()
        )

    def _update_reserved_quantity(
        self,
        need,
        location_id,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=True,
    ):
        self.ensure_one()
        if lot_id or not self._poc_restricted():
            return super()._update_reserved_quantity(
                need,
                location_id,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
            )
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        taken = 0.0
        # ядрото търси по лот с lot_id in [лот, False] (stock_quant.py
        # _get_gather_domain) — затова по един лот наведнъж, по реда на
        # партидите
        for lot in self._poc_family_lots():
            remaining = need - taken
            if float_compare(remaining, 0.0, precision_digits=digits) <= 0:
                break
            taken += super()._update_reserved_quantity(
                remaining,
                location_id,
                lot_id=lot,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
            )
        return taken

    def _get_available_move_lines(self, assigned_moves_ids, partially_available_moves_ids):
        available = super()._get_available_move_lines(
            assigned_moves_ids, partially_available_moves_ids
        )
        if not self._poc_restricted():
            return available
        family = self._poc_family_lots()
        # ключът е (location, lot, package, owner)
        return {key: qty for key, qty in available.items() if key[1] in family}

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        for move in self.filtered(lambda m: m.state == "done"):
            if not move._poc_restricted():
                continue
            stray = move.move_line_ids.lot_id - move._poc_family_lots()
            if stray:
                raise UserError(
                    self.env._(
                        "Lot %(lots)s does not belong to production configuration "
                        "%(poc)s.",
                        lots=", ".join(stray.mapped("name")),
                        poc=move.poc_id.name,
                    )
                )
        return moves
