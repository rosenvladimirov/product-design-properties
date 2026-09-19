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

from odoo import Command, models

_logger = logging.getLogger(__name__)


class MRPProduction(models.Model):
    _inherit = "mrp.production"

    def _get_move_raw_values(
        self,
        product,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        """Evaluate the BoM line quantity formula when building raw moves.

        За линия с непразна формула: вика ``_eval_quantity_formula`` и
        прилага резултата върху move стойностите. Float резултат сменя
        само количеството; dict резултат може да override-не и
        product/uom. При грешка или невалиден резултат остава
        стандартното количество от експлозията (+ warning в лога).
        """
        values = super()._get_move_raw_values(
            product,
            product_uom_qty,
            product_uom,
            operation_id=operation_id,
            bom_line=bom_line,
        )
        if not bom_line or not getattr(bom_line, "quantity_formula", False):
            return values

        try:
            result = bom_line._eval_quantity_formula(
                product,
                product_uom,
                product_uom_qty,
                self,
                operation_id=operation_id,
            )
        except Exception:
            _logger.warning(
                "Quantity formula of BoM line %s (product %s) failed; "
                "falling back to the standard exploded quantity.",
                bom_line.id,
                product.display_name,
                exc_info=True,
            )
            return values

        if result is None:
            return values

        if isinstance(result, dict):
            if result.get("skip"):
                # формулата каза "махни реда": маркер за _get_moves_raw_values;
                # stock.move.create също го чисти (за чужди пътища)
                values["formula_skip"] = True
                values["product_uom_qty"] = 0.0
                return values
            try:
                values["product_uom_qty"] = float(result.get("quantity") or 0.0)
            except (TypeError, ValueError):
                _logger.warning(
                    "Quantity formula of BoM line %s returned a non-numeric "
                    "quantity (%r); falling back to the standard quantity.",
                    bom_line.id,
                    result.get("quantity"),
                )
                return values
            if result.get("product"):
                # v19: stock.move вече няма поле 'name'
                values["product_id"] = result["product"].id
            if result.get("uom"):
                values["product_uom"] = result["uom"].id
            if result.get("add_products") and self._formula_expand_add_products(
                bom_line
            ):
                # маркер за _get_moves_raw_values: там списъкът става
                # допълнителни движения на същия ред
                values["formula_add_products"] = result["add_products"]
            return self._apply_formula_extras_to_move_values(
                values, result, bom_line
            )

        try:
            values["product_uom_qty"] = float(result)
        except (TypeError, ValueError):
            _logger.warning(
                "Quantity formula of BoM line %s returned a non-numeric "
                "result (%r); falling back to the standard quantity.",
                bom_line.id,
                result,
            )
        return values

    def _apply_formula_extras_to_move_values(self, values, result, bom_line):
        """Extension hook: разширенията прилагат своите изходи от
        формулния резултат върху move стойностите. Базата не прави нищо."""
        return values

    def _formula_expand_add_products(self, bom_line):
        """Разгръща ли се ``add_products`` на реда в допълнителни движения.

        Базата — да. Разширение, което добавя тези движения само (напр.
        матрицата при потвърждаване), връща False за своите BoM-ове, иначе
        редовете ще се удвоят.
        """
        return True

    def _get_moves_raw_values(self):
        """Стандартната експлозия с двата маркера на формулата.

        ``formula_skip`` — редът отпада изцяло (компонентът не се появява в
        MO-то). ``formula_add_products`` — след основното движение на реда
        идват допълнителните от ``add_products`` (виж
        ``_formula_extra_move_values``).
        """
        moves = []
        for vals in super()._get_moves_raw_values():
            extras = vals.pop("formula_add_products", None)
            if vals.pop("formula_skip", False):
                continue
            moves.append(vals)
            if extras:
                production = self.browse(vals["raw_material_production_id"])
                moves += production._formula_extra_move_values(vals, extras)
        return moves

    def _formula_extra_move_values(self, main_vals, items):
        """Стойностите на допълнителните движения от ``add_products``.

        Всеки елемент е dict с ``product`` (product.product или id) или
        ``ref`` (xml id), ``quantity`` (число) и по избор ``uom``. Движението
        е копие на основното — така пренася всичко, което другите модули са
        добавили към реда — с друг продукт, количество и мярка и флаг
        ``formula_extra``. Един продукт два пъти е едно движение със сбора:
        ключът на съпоставката е (ред, продукт).
        """
        self.ensure_one()
        result = []
        by_product = {}
        for item in items:
            parsed = self._formula_parse_extra_item(item, main_vals)
            if not parsed:
                continue
            product, qty, uom = parsed
            existing = by_product.get(product.id)
            if existing:
                existing_uom = self.env["uom.uom"].browse(existing["product_uom"])
                existing["product_uom_qty"] += uom._compute_quantity(
                    qty, existing_uom
                )
                continue
            vals = dict(main_vals)
            vals.update(
                {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": uom.id,
                    "formula_extra": True,
                }
            )
            by_product[product.id] = vals
            result.append(vals)
        return result

    def _formula_parse_extra_item(self, item, main_vals):
        """Един елемент на ``add_products`` → (product, qty, uom) или None."""
        line_id = main_vals.get("bom_line_id")
        if not isinstance(item, dict):
            _logger.warning(
                "add_products of BoM line %s: item %r is not a dict; skipped.",
                line_id,
                item,
            )
            return None
        product = item.get("product")
        if isinstance(product, int):
            product = self.env["product.product"].browse(product).exists()
        if not product and item.get("ref"):
            product = self.env.ref(item["ref"], raise_if_not_found=False)
        if not product or getattr(product, "_name", None) != "product.product":
            _logger.warning(
                "add_products of BoM line %s: item %r has no product; skipped.",
                line_id,
                item,
            )
            return None
        try:
            qty = float(item.get("quantity") or 0.0)
        except (TypeError, ValueError):
            _logger.warning(
                "add_products of BoM line %s: quantity %r of %s is not a "
                "number; skipped.",
                line_id,
                item.get("quantity"),
                product.display_name,
            )
            return None
        if qty <= 0.0:
            return None
        uom = item.get("uom") or product.uom_id
        return product, qty, uom

    def _compute_move_raw_ids(self):
        """Черновите MO с формулни редове съпоставят по (ред, продукт).

        Ядрото ключира движенията по ``bom_line_id`` (CORE
        mrp/models/mrp_production.py:830-838): движенията от
        ``add_products`` делят реда с основното и при всяка смяна на
        количеството ще се смачкат в едно. Ядрото не маха и движение на
        ред, който вече не дава стойности (skip). Затова за тези MO
        компютът е тук; всички останали минават през ядрото.
        """
        formula_productions = self.filtered(
            lambda p: p.state == "draft"
            and not self.env.context.get("skip_compute_move_raw_ids")
            and p.bom_id.bom_line_ids.filtered("quantity_formula")
        )
        super(MRPProduction, self - formula_productions)._compute_move_raw_ids()
        for production in formula_productions:
            production._formula_compute_move_raw_ids()

    def _formula_compute_move_raw_ids(self):
        """Компютът на ядрото с ключ (ред, продукт) и триене на изчезналите."""
        self.ensure_one()
        commands = [
            Command.link(move.id)
            for move in self.move_raw_ids.filtered(lambda m: not m.bom_line_id)
        ]
        if any(
            move.bom_line_id.bom_id != self.bom_id
            or move.bom_line_id._skip_bom_line(
                self.product_id, self.never_product_template_attribute_value_ids
            )
            for move in self.move_raw_ids
            if move.bom_line_id
        ):
            self.move_raw_ids = [Command.clear()]
        if not (self.bom_id and self.product_id and self.product_qty > 0):
            self.move_raw_ids = [
                Command.delete(move.id)
                for move in self.move_raw_ids.filtered("bom_line_id")
            ]
            return
        existing = {
            move._formula_raw_move_key(): move
            for move in self.move_raw_ids.filtered("bom_line_id")
        }
        seen = set()
        for vals in self._get_moves_raw_values():
            key = (
                vals["bom_line_id"],
                vals["product_id"] if vals.get("formula_extra") else False,
            )
            move = existing.get(key)
            if move:
                commands.append(Command.update(move.id, vals))
                seen.add(key)
            else:
                commands.append(Command.create(vals))
        commands += [
            Command.delete(move.id)
            for key, move in existing.items()
            if key not in seen
        ]
        self.move_raw_ids = commands
