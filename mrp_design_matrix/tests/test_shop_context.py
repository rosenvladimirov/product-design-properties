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
"""The shop floor context an operation carries beside its duration.

The point of the barcode field is that it survives translation, which the
operation name does not — so these tests pin that difference down.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestShopContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Operation = cls.env["mrp.routing.workcenter"]
        cls.workcenter = cls.env["mrp.workcenter"].create(
            {"name": "Test Powder Coating", "code": "TSTPWD"}
        )

    def _make_operation(self, name, **vals):
        return self.Operation.create(
            dict(name=name, workcenter_id=self.workcenter.id, **vals)
        )

    def test_one_operation_can_carry_several_barcodes(self):
        operation = self._make_operation(
            "Powder coating of profiles", shop_barcode="01/29,02/05"
        )
        self.assertEqual(operation._shop_barcode_list(), ["01/29", "02/05"])

    def test_barcode_list_tolerates_spacing_and_emptiness(self):
        operation = self._make_operation("Punching", shop_barcode=" 01/22 , ,01/05 ")
        self.assertEqual(operation._shop_barcode_list(), ["01/22", "01/05"])
        self.assertEqual(self._make_operation("No barcode")._shop_barcode_list(), [])

    def test_barcode_survives_a_translated_name(self):
        """Точката на полето: името се мени с езика, баркодът — не."""
        operation = self._make_operation(
            "Powder coating — frame", shop_barcode="01/31", semi_finished="frame_metal"
        )
        operation.with_context(lang="bg_BG").name = "Прахово боядисване — каса"
        self.assertEqual(operation.shop_barcode, "01/31")
        self.assertEqual(operation.semi_finished, "frame_metal")

    def test_barcodes_are_read_out_of_a_name(self):
        found = self.Operation._barcodes_in_name(
            "Монтаж брава + сглобяване крило (02/03,02/06)"
        )
        self.assertEqual(found, ["02/03", "02/06"])
        self.assertEqual(self.Operation._barcodes_in_name("Сглобяване"), [])
        self.assertEqual(self.Operation._barcodes_in_name(None), [])

    def test_fill_from_name_only_touches_empty_ones(self):
        empty = self._make_operation("Welding of frame (01/02)")
        taken = self._make_operation("Bending (01/24)", shop_barcode="01/99")
        plain = self._make_operation("Assembly")
        filled = (empty | taken | plain).action_fill_shop_barcode_from_name()
        self.assertEqual(empty.shop_barcode, "01/02")
        self.assertEqual(
            taken.shop_barcode, "01/99", "an existing barcode must not be overwritten"
        )
        self.assertFalse(plain.shop_barcode)
        self.assertEqual(filled, empty)

    def test_two_times_live_side_by_side(self):
        """Чистото е за себестойност, календарното — за капацитет."""
        operation = self._make_operation(
            "Precise cutting",
            time_cycle_manual=12.5,
            time_calendar=15.5,
            time_source="measured",
            shop_frequency=0.86,
        )
        self.assertEqual(operation.time_cycle_manual, 12.5)
        self.assertEqual(operation.time_calendar, 15.5)
        self.assertEqual(operation.time_source, "measured")
        self.assertAlmostEqual(operation.shop_frequency, 0.86)
