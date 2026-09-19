# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
"""
``add_products`` на формулата става допълнителни суровинни движения на
същия BoM ред, а черновото MO ги съпоставя по (ред, продукт) при всяка
смяна на количеството.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.mrp_bom_line_formula_template.models.mrp_production import (
    MRPProduction,
)


@tagged("post_install", "-at_install")
class TestAddProducts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.parent = Product.create({"name": "AP Parent", "is_storable": True})
        cls.component = Product.create({"name": "AP Component", "is_storable": True})
        cls.extra_a = Product.create({"name": "AP Extra A", "is_storable": True})
        cls.extra_b = Product.create({"name": "AP Extra B", "is_storable": True})
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.parent.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )
        cls.line = cls.env["mrp.bom.line"].create(
            {
                "bom_id": cls.bom.id,
                "product_id": cls.component.id,
                "product_qty": 1.0,
            }
        )

    def _set_formula(self, formula):
        template = self.env["mrp.bom.line.formula.template"].create(
            {"name": "add-products %s" % len(formula), "quantity_formula": formula}
        )
        self.line.formula_template_id = template

    def _make_mo(self, qty):
        return self.env["mrp.production"].create(
            {
                "product_id": self.parent.id,
                "bom_id": self.bom.id,
                "product_qty": qty,
            }
        )

    def _qty(self, mo, product):
        moves = mo.move_raw_ids.filtered(lambda m: m.product_id == product)
        return [round(m.product_uom_qty, 4) for m in moves]

    def _extra(self, product, qty_expr):
        return "{'product': env['product.product'].browse(%d), 'quantity': %s}" % (
            product.id,
            qty_expr,
        )

    def test_add_products_creates_extra_moves(self):
        """Основното движение + по едно за всеки елемент, на същия ред."""
        self._set_formula(
            "result = product_uom_qty * 2\n"
            "add_products = [%s, %s]"
            % (self._extra(self.extra_a, "3"), self._extra(self.extra_b, "0.5"))
        )
        mo = self._make_mo(2.0)
        self.assertEqual(self._qty(mo, self.component), [4.0])
        self.assertEqual(self._qty(mo, self.extra_a), [3.0])
        self.assertEqual(self._qty(mo, self.extra_b), [0.5])
        extras = mo.move_raw_ids.filtered("formula_extra")
        self.assertEqual(extras.product_id, self.extra_a | self.extra_b)
        self.assertEqual(extras.bom_line_id, self.line)
        main = mo.move_raw_ids - extras
        self.assertFalse(main.formula_extra)

    def test_draft_quantity_change_keeps_moves_apart(self):
        """Смяна на количеството на черновото MO не смачква движенията.

        Мутация: без ключа (ред, продукт) ядрото ключира по реда и
        допълнителното движение презаписва основното.
        """
        self._set_formula(
            "result = product_uom_qty\n"
            "add_products = [%s]" % self._extra(self.extra_a, "product_uom_qty * 10")
        )
        mo = self._make_mo(1.0)
        self.assertEqual(self._qty(mo, self.component), [1.0])
        self.assertEqual(self._qty(mo, self.extra_a), [10.0])
        mo.product_qty = 3.0
        self.assertEqual(self._qty(mo, self.component), [3.0])
        self.assertEqual(self._qty(mo, self.extra_a), [30.0])
        self.assertEqual(len(mo.move_raw_ids), 2)

    def test_extra_that_disappears_is_removed(self):
        """Продукт, който излиза от add_products, губи движението си."""
        self._set_formula(
            "result = product_uom_qty\n"
            "add_products = [%s] if product_uom_qty > 5 else []"
            % self._extra(self.extra_a, "1")
        )
        mo = self._make_mo(8.0)
        self.assertEqual(self._qty(mo, self.extra_a), [1.0])
        mo.product_qty = 2.0
        self.assertEqual(self._qty(mo, self.extra_a), [])
        self.assertEqual(self._qty(mo, self.component), [2.0])

    def test_skip_on_draft_recompute_removes_main_move(self):
        """Ред, станал skip в черновата, губи движението си.

        Компютът на ядрото го оставяше със старото количество.
        """
        self._set_formula("skip = product_uom_qty < 5\nresult = product_uom_qty")
        mo = self._make_mo(8.0)
        self.assertEqual(self._qty(mo, self.component), [8.0])
        mo.product_qty = 2.0
        self.assertEqual(self._qty(mo, self.component), [])

    def test_same_product_twice_is_one_move(self):
        """Един продукт два пъти в add_products е едно движение със сбора."""
        self._set_formula(
            "result = 1\n"
            "add_products = [%s, %s]"
            % (self._extra(self.extra_a, "2"), self._extra(self.extra_a, "5"))
        )
        mo = self._make_mo(1.0)
        self.assertEqual(self._qty(mo, self.extra_a), [7.0])

    def test_invalid_items_are_skipped_with_warning(self):
        """Елемент без продукт или с нечислово количество се пропуска."""
        self._set_formula(
            "result = 1\n"
            "add_products = [{'quantity': 3}, %s, %s]"
            % (
                self._extra(self.extra_a, "'many'"),
                self._extra(self.extra_b, "4"),
            )
        )
        with self.assertLogs(
            "odoo.addons.mrp_bom_line_formula_template.models.mrp_production",
            level="WARNING",
        ) as logs:
            mo = self._make_mo(1.0)
        self.assertEqual(len(logs.output), 2)
        self.assertEqual(self._qty(mo, self.extra_a), [])
        self.assertEqual(self._qty(mo, self.extra_b), [4.0])

    def test_hook_can_switch_expansion_off(self):
        """Разширение, което добавя движенията само, изключва разгръщането."""
        self._set_formula(
            "result = 1\nadd_products = [%s]" % self._extra(self.extra_a, "3")
        )
        with patch.object(
            MRPProduction, "_formula_expand_add_products", return_value=False
        ):
            mo = self._make_mo(1.0)
        self.assertEqual(self._qty(mo, self.extra_a), [])
        self.assertEqual(self._qty(mo, self.component), [1.0])

    def test_bom_without_formula_uses_core_compute(self):
        """BoM без формули минава през компюта на ядрото, както преди."""
        mo = self._make_mo(3.0)
        self.assertEqual(self._qty(mo, self.component), [3.0])
        mo.product_qty = 5.0
        self.assertEqual(self._qty(mo, self.component), [5.0])
