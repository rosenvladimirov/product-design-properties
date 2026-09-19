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
from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase


class PocCommon(TransactionCase):
    """Общата основа: речник, шаблон „торба“, продукт с лот, клиент, склад.

    Не стъпва на демо данните — тестовете минават и на база без демо.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # съобщенията се сравняват само по тип на грешката; езикът е фиксиран,
        # за да не зависят етикетите в схемата от езика на базата
        cls.env = cls.env(context=dict(cls.env.context, lang="en_US"))
        Param = cls.env["sale.order.poc.param"]
        cls.p_width = Param.create(
            {"code": "t_width_mm", "name": "Width", "param_type": "float", "suffix": "mm"}
        )
        cls.p_length = Param.create(
            {"code": "t_length_mm", "name": "Length", "param_type": "float"}
        )
        cls.p_thickness = Param.create(
            {"code": "t_thickness_um", "name": "Thickness", "param_type": "float"}
        )
        cls.p_density = Param.create(
            {
                "code": "t_density",
                "name": "Density",
                "param_type": "float",
                "default_value": "0.92",
            }
        )
        cls.p_waste = Param.create(
            {
                "code": "t_waste_pct",
                "name": "Waste",
                "param_type": "float",
                "default_value": "0",
            }
        )
        cls.p_material = Param.create(
            {
                "code": "t_material",
                "name": "Material",
                "param_type": "selection",
                "default_value": "ldpe",
                "option_ids": [
                    (0, 0, {"key": "ldpe", "name": "LDPE", "sequence": 1}),
                    (0, 0, {"key": "hdpe", "name": "HDPE", "sequence": 2}),
                ],
            }
        )
        cls.p_colors = Param.create(
            {
                "code": "t_colors",
                "name": "Colors",
                "param_type": "tags",
                "option_ids": [
                    (0, 0, {"key": "red", "name": "Red", "color": 1}),
                    (0, 0, {"key": "blue", "name": "Blue", "color": 4}),
                ],
            }
        )
        cls.p_printer = Param.create(
            {
                "code": "t_printer",
                "name": "Printer",
                "param_type": "many2one",
                "comodel": "res.partner",
            }
        )
        cls.p_weight = Param.create(
            {"code": "t_weight_g", "name": "Bag Weight", "param_type": "float", "digits": 3}
        )
        cls.p_weight_gross = Param.create(
            {"code": "t_weight_gross_g", "name": "Gross Weight", "param_type": "float"}
        )
        cls.template = cls.env["sale.order.poc.template"].create(
            {
                "code": "t_bag",
                "name": "Test Bag",
                "label_formula": (
                    "result = '%gx%g/%g' % (t_width_mm, t_length_mm, t_thickness_um)"
                ),
                "line_ids": [
                    (0, 0, {"sequence": 1, "display_type": "line_section", "name": "Size"}),
                    (0, 0, {"sequence": 2, "param_id": cls.p_width.id, "required": True}),
                    (0, 0, {"sequence": 3, "param_id": cls.p_length.id, "required": True}),
                    (0, 0, {"sequence": 4, "param_id": cls.p_thickness.id, "required": True}),
                    (0, 0, {"sequence": 5, "param_id": cls.p_density.id}),
                    (0, 0, {"sequence": 6, "param_id": cls.p_waste.id}),
                    (0, 0, {"sequence": 7, "param_id": cls.p_material.id}),
                    (0, 0, {"sequence": 8, "param_id": cls.p_colors.id}),
                    (0, 0, {"sequence": 9, "param_id": cls.p_printer.id}),
                    # брутото е преди нетото в реда на показ — формулите се
                    # смятат по зависимостите, не по sequence
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "param_id": cls.p_weight_gross.id,
                            "formula": "result = t_weight_g * (1 + t_waste_pct / 100)",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sequence": 11,
                            "param_id": cls.p_weight.id,
                            "formula": (
                                "result = 2 * t_width_mm * t_length_mm * "
                                "t_thickness_um * t_density / 1000000"
                            ),
                            "allow_manual": True,
                        },
                    ),
                ],
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Configured Bag",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
                "sale_ok": True,
                "list_price": 1.0,
                "poc_template_id": cls.template.id,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "POC Customer"})
        cls.printer = cls.env["res.partner"].create({"name": "POC Printer"})
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.salesman = new_test_user(
            cls.env,
            login="poc_salesman",
            groups="sales_team.group_sale_salesman,stock.group_stock_user",
        )
        cls.manager = new_test_user(
            cls.env,
            login="poc_manager",
            groups="sales_team.group_sale_manager,stock.group_stock_user",
        )

    def _make_order(self, qty=1000.0, product=None):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": (product or self.product).id,
                            "product_uom_qty": qty,
                        },
                    )
                ],
            }
        )

    def _make_poc(self, order=None, **params):
        order = order or self._make_order()
        poc = self.env["sale.order.poc"].create({"sale_line_id": order.order_line.id})
        if params:
            poc._poc_set_params(params)
            poc._poc_compute_derived()
        return poc

    def _fill(self, poc, width=300.0, length=500.0, thickness=20.0):
        poc.write(
            {
                "params": {
                    **(poc.params._values or {}),
                    "t_width_mm": width,
                    "t_length_mm": length,
                    "t_thickness_um": thickness,
                }
            }
        )
        return poc
