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
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PocMrpCommon


@tagged("post_install", "-at_install")
class TestMoLink(PocMrpCommon):
    def test_mo_carries_configuration(self):
        """MO от продажбата носи POC, лота му и резюмето; договорът е пред
        двигателя още при експлозията при създаване."""
        with self._engine() as seen:
            order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        self.assertEqual(len(production), 1)
        self.assertEqual(production.poc_id, poc)
        self.assertEqual(production.lot_producing_ids, poc.lot_id)
        self.assertIn(poc.summary, production.product_description_variants)
        self.assertTrue(seen, "the engine never saw the contract")
        self.assertEqual(seen[0]["t_width_mm"], 300.0)
        self.assertEqual(seen[0]["lot"], poc.lot_id)
        # 300 × 500 / 10 000 × 10 + 5
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 155.0)
        self.assertEqual(self._raw(production, self.film).poc_id, poc)

    def test_second_configuration_gets_its_own_order(self):
        """Втори ред със същия продукт, добавен към потвърдената поръчка:
        ядрото търси съществуващо MO по домейна и без POC в него би
        сляло двата реда в едно MO (едно MO с 30)."""
        order, poc_a = self._confirmed_order(qty=10.0)
        order.write(
            {
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 20.0})
                ]
            }
        )
        line_b = order.order_line.filtered(lambda l: not l.poc_id)
        poc_b = self._fill(self.env["sale.order.poc"].create({"sale_line_id": line_b.id}))
        poc_b.action_release()
        productions = (poc_a | poc_b).production_ids
        self.assertEqual(len(productions), 2)
        self.assertEqual(poc_a.production_ids.product_qty, 10.0)
        self.assertEqual(poc_b.production_ids.product_qty, 20.0)

    def test_more_quantity_merges_absolutely(self):
        """Още количество по същия POC отива в същото MO и суровината се
        смята наново, не линейно: 15 × 20 + 5, не 155 × 2."""
        with self._engine():
            order, poc = self._confirmed_order(qty=10.0)
            order.order_line.product_uom_qty = 20.0
        production = poc.production_ids
        self.assertEqual(len(production), 1)
        self.assertEqual(production.product_qty, 20.0)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 305.0)

    def test_component_sub_mo_gets_its_lot(self):
        """Произведеният по POC компонент получава лот от семейството, а
        родителят го резервира само оттам."""
        self._make_film_manufactured()
        order, poc = self._confirmed_order(qty=10.0)
        productions = poc.production_ids
        sub = productions.filtered(lambda p: p.product_id == self.film)
        main = productions - sub
        self.assertEqual(len(sub), 1)
        self.assertEqual(sub.poc_id, poc)
        self.assertEqual(sub.lot_producing_ids.poc_id, poc)
        self.assertEqual(sub.lot_producing_ids.product_id, self.film)
        self.assertEqual(main.lot_producing_ids, poc.lot_id)
        self.assertTrue(self._raw(main, self.film).poc_lot_restrict)
        # мастилото се взема от склада: без ограничение
        self.assertFalse(self._raw(main, self.ink).poc_lot_restrict)

    def test_component_restriction_in_two_steps(self):
        """pbm: подаването към производството и суровината — и двете
        движения вземат само от семейството."""
        self.warehouse.manufacture_steps = "pbm"
        self._make_film_manufactured()
        order, poc = self._confirmed_order(qty=10.0)
        main = poc.production_ids.filtered(lambda p: p.product_id == self.product)
        raw = self._raw(main, self.film)
        feed = raw.move_orig_ids
        self.assertTrue(feed, "no pick-components move before the raw material")
        self.assertTrue(raw.poc_lot_restrict)
        self.assertTrue(feed.poc_lot_restrict)
        sub = poc.production_ids - main
        self.assertEqual(sub.lot_producing_ids.poc_id, poc)

    def test_component_lots_free_without_the_flag(self):
        self.template.restrict_component_lots = False
        self._make_film_manufactured()
        order, poc = self._confirmed_order(qty=10.0)
        main = poc.production_ids.filtered(lambda p: p.product_id == self.product)
        self.assertFalse(self._raw(main, self.film).poc_lot_restrict)

    def test_force_mts_component_is_taken_from_stock(self):
        self._make_film_manufactured()
        self.line_film.force_mts = True
        order, poc = self._confirmed_order(qty=10.0)
        self.assertEqual(poc.production_ids.product_id, self.product)
        self.assertEqual(
            self._raw(poc.production_ids, self.film).procure_method, "make_to_stock"
        )

    def test_backorder_keeps_the_lot(self):
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        film_lot = self.env["stock.lot"].create(
            {"product_id": self.film.id, "name": "FILM-A"}
        )
        self._stock(self.film, 100.0, film_lot)
        self._stock(self.ink, 100.0)
        backorder = self._produce(production, 4.0)
        self.assertEqual(backorder.poc_id, poc)
        self.assertEqual(backorder.lot_producing_ids, poc.lot_id)
        self._produce(backorder, 6.0)
        picking = order.picking_ids
        picking.action_assign()
        self.assertAlmostEqual(picking.move_ids.quantity, 10.0)
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, poc.lot_id)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_backorder_with_batches_gets_the_next_batch(self):
        self.template.lot_batches = True
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        film_lot = self.env["stock.lot"].create(
            {"product_id": self.film.id, "name": "FILM-B"}
        )
        self._stock(self.film, 100.0, film_lot)
        self._stock(self.ink, 100.0)
        backorder = self._produce(production, 4.0)
        self.assertEqual(backorder.lot_producing_ids.poc_id, poc)
        self.assertEqual(backorder.lot_producing_ids.poc_batch, 2)
        self._produce(backorder, 6.0)
        picking = order.picking_ids
        picking.action_assign()
        self.assertAlmostEqual(picking.move_ids.quantity, 10.0)
        self.assertEqual(
            picking.move_ids.move_line_ids.lot_id,
            poc.lot_id | backorder.lot_producing_ids,
        )
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_merge_needs_one_configuration(self):
        order_a, poc_a = self._confirmed_order(qty=10.0)
        order_b, poc_b = self._confirmed_order(qty=10.0)
        with self.assertRaises(UserError):
            (poc_a.production_ids | poc_b.production_ids).action_merge()

    def test_merge_of_one_configuration_keeps_it(self):
        order, poc = self._confirmed_order(qty=10.0)
        production = poc.production_ids
        parts = production._split_productions({production: [4.0, 6.0]})
        self.assertEqual(parts.poc_id, poc)
        res = parts.action_merge()
        merged = self.env["mrp.production"].browse(res["res_id"])
        self.assertEqual(merged.poc_id, poc)
        self.assertEqual(merged.lot_producing_ids, poc.lot_id)
        self.assertEqual(merged.product_qty, 10.0)

    def test_serial_joins_the_family(self):
        self.product.tracking = "serial"
        order, poc = self._confirmed_order(qty=2.0)
        vals = poc.production_ids._prepare_stock_lot_values()
        self.assertEqual(vals["poc_id"], poc.id)
        self.assertEqual(vals["poc_batch"], 1)

    def test_mo_without_configuration_is_standard(self):
        with self._engine() as seen:
            production = self.env["mrp.production"].create(
                {"product_id": self.product.id, "product_qty": 10.0, "bom_id": self.bom.id}
            )
        self.assertFalse(production.poc_id)
        self.assertFalse(seen)
        self.assertAlmostEqual(self._raw(production, self.film).product_uom_qty, 20.0)
        self.assertFalse(self._raw(production, self.film).poc_id)
