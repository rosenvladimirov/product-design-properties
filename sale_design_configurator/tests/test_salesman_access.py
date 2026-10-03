# Copyright 2026 Rosen Vladimirov, Terraros Commerce Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Търговец без „Инвентар / Потребител“ минава целия път на конфигуратора.

Пътят е този, по който кликва търговецът (Атанас, 23.09.2026, msg 167191):
избор на модела в реда → „Конфигурирай“ (дефиниция, профили, операции) →
име и запис на партидата → „Confirm (Sales)“. Всяка стъпка е с правата на
потребителя, без sudo — както я вика JS-ът.

Търговецът е САМО „Продажби + Design / Sales“: складовата група му дава
приемане и експедиция в целия склад, затова не е решение.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

PREFIX_UUID = "5a1e5a1e0c0f4e11"
SERIES_UUID = "5a1e5a1e0c0f4e12"


@tagged("post_install", "-at_install")
class TestSalesmanAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "test_salesman_access",
                "name": "Test Salesman Access",
                "design_params_definition": [
                    {"name": PREFIX_UUID, "type": "char", "string": "Lot Prefix"},
                    {"name": SERIES_UUID, "type": "char", "string": "Series"},
                ],
                "param_dictionary": {
                    "lot_prefix": {"uuid": PREFIX_UUID, "name": {}, "aliases": []},
                    "series": {"uuid": SERIES_UUID, "name": {}, "aliases": []},
                },
            }
        )
        cls.profile = cls.env["design.param.profile"].create(
            {"name": "Test Profile", "definition_id": cls.definition.id}
        )
        # Шаблон за префикс ⇒ всяка нова комбинация ражда СВОЯ поредица —
        # това е пътят, по който името създава ir.sequence.
        cls.door = cls.env["product.product"].create(
            {
                "name": "Salesman Door",
                "is_storable": True,
                "tracking": "lot",
                "design_param_definition_id": cls.definition.id,
                "design_properties": {PREFIX_UUID: "{series}"},
            }
        )
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Test Paint"})
        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.door.product_tmpl_id.id,
                "product_qty": 1.0,
                # празна, но валидна таблица — операциите се търсят само
                # при рецепта с матрица
                "material_table": {
                    "nodes": [
                        {
                            "id": "t",
                            "name": "T2",
                            "type": "decisionTable",
                            "content": {
                                "hitPolicy": "collect",
                                "inputs": [],
                                "outputs": [],
                                "rules": [],
                            },
                        }
                    ],
                    "edges": [],
                },
                "operation_choices_def": [
                    {"key": "paint", "name": "Paint", "wc": cls.workcenter.id}
                ],
            }
        )
        cls.plain = cls.env["product.product"].create(
            {"name": "Plain Lot Product", "is_storable": True, "tracking": "lot"}
        )
        cls.plain_lot = cls.env["stock.lot"].create(
            {"name": "PLAIN-1", "product_id": cls.plain.id}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Salesman Customer"})
        cls.salesman = new_test_user(
            cls.env,
            login="design_salesman",
            groups=(
                "sales_team.group_sale_salesman,"
                "sale_design_configurator.group_design_sales"
            ),
        )

    def test_salesman_is_not_a_stock_user(self):
        """Предпоставката на целия клас: иначе тестът мери складовите права."""
        self.assertFalse(self.salesman.has_group("stock.group_stock_user"))

    def test_choosing_the_model_finds_the_definition(self):
        env = self.env(user=self.salesman)
        order = env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [Command.create({"product_id": self.door.id})],
            }
        )
        line = order.order_line
        self.assertTrue(line.has_design_definition)
        self.assertEqual(line.design_param_definition_id, self.definition)
        # формата показва името на дефиницията — и то се чете с правата му
        self.assertEqual(
            line.design_param_definition_id.display_name,
            self.definition.display_name,
        )

    def test_the_configurator_opens(self):
        env = self.env(user=self.salesman)
        # design_configurator_dialog.js — дефиницията и профилите
        env["design.param.definition"].browse(self.definition.id).read(
            ["name", "design_params_definition"]
        )
        profiles = env["design.param.profile"].search_read(
            [("definition_id", "=", self.definition.id)], ["name"]
        )
        self.assertEqual([p["id"] for p in profiles], self.profile.ids)
        # операциите: без право празният списък идваше ТИХО (try/catch в JS)
        choices = env["mrp.bom"].get_operation_choices(self.door.id)
        self.assertEqual(
            [(c["opKey"], c["wcName"]) for c in choices], [("paint", "Test Paint")]
        )

    def test_the_design_lot_is_saved_and_confirmed(self):
        env = self.env(user=self.salesman)
        Lot = env["stock.lot"]
        params = {PREFIX_UUID: "СТ", SERIES_UUID: "СТ"}
        name = Lot.generate_design_lot_name(self.door.id, params, self.definition.id)
        self.assertTrue(name.startswith("СТ"), name)
        lot = Lot.create(
            {
                "name": name,
                "product_id": self.door.id,
                "design_param_definition_id": self.definition.id,
                "design_params": params,
            }
        )
        lot.write({"matrix_operation_choices": ["paint"]})
        lot.action_design_sales_confirm()
        self.assertEqual(lot.design_state, "sales_confirmed")

    def test_salesman_cannot_touch_an_ordinary_lot(self):
        """Правото е за ДИЗАЙН партидите, не за склада."""
        lot = self.plain_lot.with_user(self.salesman)
        with self.assertRaises(AccessError):
            lot.write({"note": "не е негова"})
        with self.assertRaises(AccessError):
            self.env["stock.lot"].with_user(self.salesman).create(
                {"name": "PLAIN-2", "product_id": self.plain.id}
            )

    def test_stock_user_in_design_sales_keeps_the_whole_warehouse(self):
        """Правилото за Design / Sales не бива да стеснява складовия потребител."""
        storekeeper = new_test_user(
            self.env,
            login="design_storekeeper",
            groups=(
                "stock.group_stock_user,"
                "sale_design_configurator.group_design_sales"
            ),
        )
        self.plain_lot.with_user(storekeeper).write({"note": "складово"})
        self.assertEqual(self.plain_lot.note, "<p>складово</p>")
