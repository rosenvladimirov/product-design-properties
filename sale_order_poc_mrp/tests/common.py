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
from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command
from odoo.tests import Form

from odoo.addons.sale_order_poc.tests.common import PocCommon


class PocMrpCommon(PocCommon):
    """Продукт по POC, произвеждан по поръчка, с BoM от фолио и мастило.

    Количествата са реалистични: при нулево количество ядрото заобикаля
    експлозията и мутацията дава фалшиво зелено.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.route_mto = cls.warehouse.mto_pull_id.route_id
        cls.route_mto.active = True
        cls.route_manufacture = cls.warehouse.manufacture_pull_id.route_id
        cls.product.route_ids = [
            Command.set((cls.route_mto | cls.route_manufacture).ids)
        ]
        Product = cls.env["product.product"]
        cls.film = Product.create(
            {
                "name": "POC Film",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.ink = Product.create(
            {"name": "POC Ink", "type": "consu", "is_storable": True}
        )
        cls.granulate = Product.create(
            {"name": "POC Granulate", "type": "consu", "is_storable": True}
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create({"product_id": cls.film.id, "product_qty": 2.0}),
                    Command.create({"product_id": cls.ink.id, "product_qty": 1.0}),
                ],
            }
        )
        cls.line_film = cls.bom.bom_line_ids.filtered(lambda l: l.product_id == cls.film)
        cls.line_ink = cls.bom.bom_line_ids - cls.line_film

    # ── Помощници ────────────────────────────────────────────────────

    def _confirmed_order(self, qty=10.0, width=300.0, length=500.0):
        order = self._make_order(qty=qty)
        poc = self._fill(self._make_poc(order), width=width, length=length)
        order.action_confirm()
        return order, poc

    def _raw(self, production, product):
        return production.move_raw_ids.filtered(
            lambda m: m.product_id == product and m.state != "cancel"
        )

    def _make_film_manufactured(self):
        """Фолиото се произвежда по поръчка: под-MO на същия POC."""
        self.film.route_ids = [
            Command.set((self.route_mto | self.route_manufacture).ids)
        ]
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.film.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create({"product_id": self.granulate.id, "product_qty": 1.0})
                ],
            }
        )

    def _stock(self, product, qty, lot=None):
        self.env["stock.quant"]._update_available_quantity(
            product, self.stock_location, qty, lot_id=lot
        )

    def _produce(self, production, qty):
        """Частично производство с бекордер; връща бекордера."""
        production.action_assign()
        mo_form = Form(production)
        mo_form.qty_producing = qty
        production = mo_form.save()
        action = production.button_mark_done()
        if isinstance(action, dict) and action.get("res_model") == "mrp.production.backorder":
            Form(
                self.env["mrp.production.backorder"].with_context(**action["context"])
            ).save().action_backorder()
        return production.production_group_id.production_ids - production

    @contextmanager
    def _engine(self):
        """Стъб на формулния двигател: фолиото е площта на плика по броя плюс
        5 за настройка — нелинейно. Чете само договора на MO; записва
        какво е видял, за да се провери, че договорът е там още при
        експлозията при създаване.
        """
        Production = self.env.registry["mrp.production"]
        original = Production._get_move_raw_values
        seen = []
        line_film = self.line_film

        def engine(
            production, product, qty, uom, operation_id=False, bom_line=False
        ):
            vals = original(production, product, qty, uom, operation_id, bom_line)
            if production.poc_id and bom_line == line_film:
                contract = production._poc_formula_context()
                seen.append(contract)
                vals["product_uom_qty"] = (
                    contract["t_width_mm"] * contract["t_length_mm"] / 10000.0
                ) * contract["mo_qty"] + 5.0
            return vals

        with patch.object(Production, "_get_move_raw_values", engine):
            yield seen
