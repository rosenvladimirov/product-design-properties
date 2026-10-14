"""Новата партида взима набора на категорията (Росен, 14.10.2026)."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCategoryLotParam(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = cls.env["design.param.definition"].create({
            "code": "test_lot_sheet",
            "name": "Sheet metal lot (test)",
            "design_params_definition": [
                {"name": "a1b2c3d4e5f60001", "type": "float", "string": "Net weight, kg"},
                {"name": "a1b2c3d4e5f60002", "type": "char", "string": "Heat number"},
            ],
        })
        cls.parent = cls.env["product.category"].create(
            {"name": "Metal (test)", "lot_param_definition_id": cls.definition.id})
        cls.child = cls.env["product.category"].create({"name": "Sheets (test)", "parent_id": cls.parent.id})
        cls.plain = cls.env["product.category"].create({"name": "Other (test)"})

    def _lot(self, categ, **vals):
        product = self.env["product.product"].create(
            {"name": "P %s" % categ.name, "is_storable": True, "tracking": "lot", "categ_id": categ.id})
        return self.env["stock.lot"].create(dict({"name": "L-%s" % product.id, "product_id": product.id}, **vals))

    def test_naborat_idva_ot_kategoriyata(self):
        self.assertEqual(self._lot(self.parent).design_param_definition_id, self.definition)

    def test_podkategoriyata_go_nasledyava(self):
        self.assertEqual(self._lot(self.child).design_param_definition_id, self.definition)

    def test_bez_nabor_na_kategoriyata(self):
        self.assertFalse(self._lot(self.plain).design_param_definition_id)

    def test_izrichniyat_nabor_ne_se_pipa(self):
        other = self.env["design.param.definition"].create({"code": "test_other", "name": "Other (test)"})
        self.assertEqual(self._lot(self.parent, design_param_definition_id=other.id).design_param_definition_id, other)
