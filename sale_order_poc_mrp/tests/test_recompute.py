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
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestRecompute(PocMrpCommon):
    def _change_qty(self, production, qty):
        self.env["change.production.qty"].create(
            {"mo_id": production.id, "product_qty": qty}
        ).change_prod_qty()

    def _write_width(self, poc, width):
        poc.with_user(self.manager).write(
            {"params": {**(poc.params._values or {}), "t_width_mm": width}}
        )

    def test_change_quantity_is_absolute(self):
        """Ядрото мащабира линейно (155 × 2 = 310); по POC е 15 × 20 + 5."""
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            production = poc.production_ids
            self._change_qty(production, 20.0)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 305.0)
        self.assertAlmostEqual(self._raw(production, self.ink).product_uom_qty, 20.0)

    def test_update_bom_keeps_the_configuration(self):
        """Update BoM връща статичното (2 × 10); мостът пуска експлозията."""
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            production = poc.production_ids
            production._link_bom(production.bom_id)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 155.0)

    def test_poc_change_recomputes_an_unstarted_order(self):
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            production = poc.production_ids
            self._write_width(poc, 400.0)
        # 400 × 500 / 10 000 × 10 + 5
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 205.0)
        self.assertIn("205", production.message_ids[0].body)
        self.assertFalse(production.activity_ids)

    def test_poc_change_on_a_started_order_asks_the_planner(self):
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            production = poc.production_ids
            film = self._raw(production, self.film)
            film.write({"quantity": 50.0, "picked": True})
            self._write_width(poc, 400.0)
            self.assertAlmostEqual(film.product_uom_qty, 155.0)
            self.assertEqual(len(production.activity_ids), 1)
            # вторият запис не трупа втора задача
            self._write_width(poc, 410.0)
            self.assertEqual(len(production.activity_ids), 1)
            production.action_poc_recompute()
        # 410 × 500 / 10 000 × 10 + 5
        self.assertAlmostEqual(film.product_uom_qty, 210.0)
        self.assertFalse(production.activity_ids)

    def test_recompute_never_below_consumed(self):
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            production = poc.production_ids
            film = self._raw(production, self.film)
            film.write({"quantity": 150.0, "picked": True})
            self._write_width(poc, 100.0)
            # 100 × 500 / 10 000 × 10 + 5 = 55 < 150
            with self.assertRaises(UserError):
                production.action_poc_recompute()
        self.assertAlmostEqual(film.product_uom_qty, 155.0)

    def test_line_that_disappears_goes_to_zero(self):
        """Ред, който двигателят вече не дава (skip), отива на 0, не се трие."""
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        ink = self._raw(production, self.ink)
        Production = self.env.registry["mrp.production"]
        original = Production._get_moves_raw_values
        line_ink = self.line_ink

        def without_ink(productions):
            return [v for v in original(productions) if v["bom_line_id"] != line_ink.id]

        with patch.object(Production, "_get_moves_raw_values", without_ink):
            self._write_width(poc, 400.0)
        self.assertTrue(ink.exists())
        self.assertEqual(ink.product_uom_qty, 0.0)

    def test_two_moves_of_one_line_stay_apart(self):
        """add_products: един ред, два продукта — съпоставката е по
        (ред, продукт) и допълнителният ход се ражда и пази."""
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        Production = self.env.registry["mrp.production"]
        original = Production._get_moves_raw_values
        line_film = self.line_film
        granulate = self.granulate

        def with_extra(productions):
            values = original(productions)
            extra = dict(next(v for v in values if v["bom_line_id"] == line_film.id))
            extra.update(product_id=granulate.id, product_uom_qty=7.0)
            return values + [extra]

        with patch.object(Production, "_get_moves_raw_values", with_extra):
            self._write_width(poc, 400.0)
            self._write_width(poc, 410.0)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 20.0)
        extra = self._raw(production, self.granulate)
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra.bom_line_id, self.line_film)
        self.assertAlmostEqual(extra.product_uom_qty, 7.0)
        self.assertEqual(extra.state, "confirmed")

    def _film_orders(self, poc):
        main = poc.production_ids.filtered(lambda p: p.product_id == self.product)
        return main, poc.production_ids - main

    def test_component_order_follows_the_need(self):
        """Под-MO на същия POC следва нуждата нагоре и надолу (ADR
        sale-order-poc/0016). Ядрото само го увеличава, а при намаление го
        оставя голямо."""
        self._make_film_manufactured()
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            main, sub = self._film_orders(poc)
            self.assertAlmostEqual(sub.product_qty, 155.0)
            self._write_width(poc, 400.0)
            self.assertAlmostEqual(self._raw(main, self.film).product_uom_qty, 205.0)
            self.assertAlmostEqual(sub.product_qty, 205.0)
            self._write_width(poc, 200.0)
        self.assertAlmostEqual(self._raw(main, self.film).product_uom_qty, 105.0)
        self.assertAlmostEqual(sub.product_qty, 105.0)
        self.assertEqual(self._film_orders(poc)[1], sub)
        self.assertFalse(sub.activity_ids)

    def test_started_component_order_asks_the_planner(self):
        self._make_film_manufactured()
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            main, sub = self._film_orders(poc)
            self._raw(sub, self.granulate).write({"quantity": 10.0, "picked": True})
            self._write_width(poc, 200.0)
        self.assertAlmostEqual(self._raw(main, self.film).product_uom_qty, 105.0)
        self.assertAlmostEqual(sub.product_qty, 155.0)
        self.assertEqual(len(sub.activity_ids), 1)
        self.assertIn("105", sub.activity_ids.note)
