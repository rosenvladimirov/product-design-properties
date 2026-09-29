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
from odoo.addons.sale_order_poc.tests.common import PocCommon

# ключовете на свойствата в партидата: UUID-та, както ги ражда матрицата
U = {
    "t_width_mm": "c0ffee0000000001",
    "t_length_mm": "c0ffee0000000002",
    "t_material": "c0ffee0000000003",
    "t_board": "c0ffee0000000004",
    "t_trim_waste": "c0ffee0000000005",
    "t_printer": "c0ffee0000000006",
    "sizes": "c0ffee0000000007",
}
BOARD = "Brown C"


class MatrixPocCommon(PocCommon):
    """Торбата на POC плюс дизайн дефиниция на рецептата ѝ.

    Имената в дефиницията съвпадат с кодовете на POC за ширината,
    дължината, материала, картона и печатаря; дебелината и плътността са
    само на POC, отпадъкът от обрязване — само на матрицата.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create(
            {"name": "Test Board", "value_ids": [(0, 0, {"name": BOARD})]}
        )
        board_template = cls.env["product.template"].create(
            {
                "name": "Test Board",
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, attribute.value_ids.ids)],
                        },
                    )
                ],
            }
        )
        cls.board = board_template.product_variant_ids[:1]
        cls.p_board = cls.env["sale.order.poc.param"].create(
            {
                "code": "t_board",
                "name": "Board",
                "param_type": "many2one",
                "comodel": "product.product",
            }
        )
        cls.template.line_ids = [(0, 0, {"sequence": 20, "param_id": cls.p_board.id})]
        cls.definition = cls.env["design.param.definition"].create(
            {
                "code": "test_poc_design_matrix",
                "name": "Test POC Design Matrix",
                "design_params_definition": [
                    {"name": U["sizes"], "type": "separator", "string": "Sizes"},
                    {
                        "name": U["t_width_mm"],
                        "type": "float",
                        "string": "t_width_mm",
                        "default": 100.0,
                    },
                    {
                        "name": U["t_length_mm"],
                        "type": "float",
                        "string": "t_length_mm",
                        "default": 200.0,
                    },
                    {
                        "name": U["t_material"],
                        "type": "selection",
                        "string": "t_material",
                        "selection": [["ldpe", "LDPE"], ["hdpe", "HDPE"]],
                        "default": "ldpe",
                    },
                    {
                        "name": U["t_board"],
                        "type": "selection",
                        "string": "t_board",
                        "selection": [["White B", "White B"], [BOARD, BOARD]],
                    },
                    {
                        "name": U["t_trim_waste"],
                        "type": "float",
                        "string": "t_trim_waste",
                        "default": 0.05,
                    },
                    # запис на POC срещу параметър, който не е избор
                    {"name": U["t_printer"], "type": "char", "string": "t_printer"},
                ],
            }
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "product_qty": 1.0,
                "design_param_definition_id": cls.definition.id,
            }
        )

    def _poc_for_matrix(self, qty=1000.0, **params):
        """Поръчка с POC: размерите, HDPE и картонът — стойности на POC."""
        order = self._make_order(qty=qty)
        poc = self._fill(self._make_poc(order))
        poc._poc_set_params({"t_material": "hdpe", "t_board": self.board.id, **params})
        poc._poc_compute_derived()
        return order, poc
