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
import base64
import re

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.sale_order_poc.tests.common import PocCommon

from ..drawing_helpers import make_helpers
from ..models.sale_order_poc_drawing import SIMPLE_TYPES

LOGGER = "odoo.addons.sale_order_poc_drawing.models.sale_order_poc_drawing"

# правоъгълник по ширината и дължината; цветът — от продукта (картона);
# текстовете — селекцията и many2one, както ги вижда шаблонът
TEST_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100%"
     t-att-viewBox="d.viewbox(d.rect(0, 0, d.num(v.get('t_width_mm')), d.num(v.get('t_length_mm'))))">
    <polygon class="body"
             t-att-points="d.pts(d.rect(0, 0, d.num(v.get('t_width_mm')), d.num(v.get('t_length_mm'))))"
             t-att-fill="d.color('t_board', '#ffffff')"
             t-att-stroke="d.color('t_material', '#111111')"/>
    <text class="material" t-out="v.get('t_material')"/>
    <text class="printer" t-out="v.get('t_printer')"/>
</svg>"""

# 1×1 PNG
PIXEL = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
)


def _points(svg):
    """Точките на тялото (``class="body"``)."""
    match = re.search(r'class="body"[^>]*points="([^"]+)"', str(svg)) or re.search(
        r'points="([^"]+)"[^>]*class="body"', str(svg)
    )
    return match and match.group(1)


@tagged("post_install", "-at_install")
class TestDrawing(PocCommon):
    """Рисунката на изделието като данни на шаблона (SPEC sale-order-poc/drawing § 4)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.p_board = cls.env["sale.order.poc.param"].create(
            {
                "code": "t_board",
                "name": "Board",
                "param_type": "many2one",
                "comodel": "product.product",
            }
        )
        cls.template.line_ids = [(0, 0, {"sequence": 20, "param_id": cls.p_board.id})]
        cls.drawing = cls.env["sale.order.poc.drawing"].create(
            {
                "name": "Test rectangle",
                "code": "t_rect",
                "svg": TEST_SVG,
                "parameter_codes": "t_width_mm, t_length_mm, t_board",
                "sample_values": {"t_width_mm": 40, "t_length_mm": 20},
            }
        )
        cls.template.write(
            {
                "drawing_template_id": cls.drawing.id,
                "drawing_defaults": "t_width_mm=111, t_length_mm=222",
                "drawing_caption": "{{ t_width_mm }} × {{ t_length_mm }}",
            }
        )

    def test_01_picture_wins_over_the_svg_template(self):
        """Качената картинка печели пред SVG шаблона.

        Мутация: размени реда в `_poc_drawing` (SVG преди картинката).
        """
        self.template.drawing_picture = PIXEL
        poc = self._fill(self._make_poc())
        drawing = poc._poc_drawing()
        self.assertTrue(drawing["url"].startswith("data:image/"))
        self.assertNotIn("svg", drawing)
        self.assertEqual(
            poc.drawing_url,
            "/web/image/sale.order.poc.template/%d/drawing_picture" % self.template.id,
        )
        self.assertFalse(poc.drawing_svg)

    def test_02_the_svg_sees_the_values_by_code(self):
        """Шаблонът вижда записаните стойности по код; сменен размер сменя точките.

        Мутация: подай `drawing_defaults` вместо стойностите (махни записаните
        от `_poc_drawing_merged`).
        """
        poc = self._fill(self._make_poc(), width=300.0, length=500.0)
        svg = poc._poc_drawing()["svg"]
        self.assertEqual(_points(svg), "0.0,0.0 300.0,0.0 300.0,500.0 0.0,500.0")
        poc._poc_set_params({"t_width_mm": 450.0})
        self.assertEqual(
            _points(poc._poc_drawing()["svg"]), "0.0,0.0 450.0,0.0 450.0,500.0 0.0,500.0"
        )
        # формата на POC показва същото
        self.assertIn("450.0,0.0", str(poc.drawing_svg))

    def test_03_unsaved_values_draw_without_writing(self):
        """Незаписаните стойности рисуват, без да пишат.

        Мутация: `values` се пренебрегва в `_poc_drawing_merged`.
        """
        poc = self._fill(self._make_poc(), width=300.0, length=500.0)
        before = poc._poc_values()
        params_before = dict(poc.params._values or {})
        svg = poc._poc_drawing({"t_width_mm": 777.0})["svg"]
        self.assertEqual(_points(svg), "0.0,0.0 777.0,0.0 777.0,500.0 0.0,500.0")
        self.assertEqual(poc._poc_values(), before)
        self.assertEqual(dict(poc.params._values or {}), params_before)
        # изчистеното в касата поле рисува с подразбирането, не със записаното
        svg = poc._poc_drawing({"t_width_mm": None})["svg"]
        self.assertEqual(_points(svg), "0.0,0.0 111.0,0.0 111.0,500.0 0.0,500.0")

    def test_04_defaults_draw_an_empty_configuration(self):
        """Подразбирането рисува празната конфигурация (и надписа).

        Мутация: махни сливането с `drawing_defaults`.
        """
        poc = self._make_poc()
        self.assertIsNone(poc._poc_values()["t_width_mm"])
        drawing = poc._poc_drawing()
        self.assertEqual(_points(drawing["svg"]), "0.0,0.0 111.0,0.0 111.0,222.0 0.0,222.0")
        self.assertEqual(drawing["caption"], "111 mm × 222")

    def test_05_a_broken_template_is_empty_and_warns(self):
        """Грешка в шаблона връща празно и WARNING; формата не пада.

        Мутация: махни try/except в `_render_svg`.
        """
        poc = self._fill(self._make_poc())
        for broken in (
            '<svg xmlns="http://www.w3.org/2000/svg"><t t-out="d.nope()"/></svg>',
            "<svg><polygon></svg>",
        ):
            self.drawing.svg = broken
            with self.assertLogs(LOGGER, "WARNING") as logs:
                self.assertFalse(poc._poc_drawing())
            self.assertIn("t_rect", logs.output[0])
            poc.invalidate_recordset(["drawing_svg"])
            with self.assertLogs(LOGGER, "WARNING"):
                self.assertFalse(poc.drawing_svg)

    def test_06_the_template_sees_no_records(self):
        """`v` съдържа само прости типове: many2one е име, селекцията — ключ.

        Мутация: подай many2one като запис в `_poc_drawing_values`.
        """
        board = self.env["product.product"].create({"name": "Board B3"})
        poc = self._fill(self._make_poc())
        poc._poc_set_params(
            {"t_printer": self.printer.id, "t_material": "hdpe", "t_board": board.id}
        )
        v = poc._poc_drawing_values(poc._poc_drawing_merged())
        for code, value in v.items():
            self.assertIsInstance(value, SIMPLE_TYPES, code)
        self.assertEqual(v["t_printer"], "POC Printer")
        self.assertEqual(v["t_board"], "Board B3")
        self.assertEqual(v["t_material"], "hdpe")
        svg = str(poc._poc_drawing()["svg"])
        self.assertIn('<text class="printer">POC Printer</text>', svg)
        self.assertIn('<text class="material">hdpe</text>', svg)
        # помощниците са чисти функции: нито env, нито записи
        helpers = vars(make_helpers(v))
        self.assertTrue(all(callable(helper) for helper in helpers.values()))
        self.assertNotIn("env", helpers)

    def test_07_the_colour_comes_from_the_field_not_the_name(self):
        """Цветът идва от полето `drawing_color`, не от думи в името.

        Мутация: върни познаването по име („black“ в името → черно).
        """
        Product = self.env["product.product"]
        green = Product.create({"name": "Black Kraft Board", "drawing_color": "#00aa00"})
        plain = Product.create({"name": "Black Board"})
        self.p_material.option_ids.filtered(lambda o: o.key == "hdpe").drawing_color = "#0000ff"
        poc = self._fill(self._make_poc())
        poc._poc_set_params({"t_board": green.id, "t_material": "hdpe"})
        svg = str(poc._poc_drawing()["svg"])
        self.assertIn('fill="#00aa00"', svg)
        self.assertIn('stroke="#0000ff"', svg)
        poc._poc_set_params({"t_board": plain.id, "t_material": "ldpe"})
        svg = str(poc._poc_drawing()["svg"])
        # без цвят в полето — подразбирането на шаблона, каквото и да пише в името
        self.assertIn('fill="#ffffff"', svg)
        self.assertIn('stroke="#111111"', svg)

    def test_10_the_pdf_block_has_a_fixed_size(self):
        """PDF подшаблонът: SVG с фиксирана ширина и височина за wkhtmltopdf.

        Мутация: махни стила `svg { width: 90mm; height: 55mm; }`.
        """
        poc = self._fill(self._make_poc())
        html = str(
            self.env["ir.qweb"]._render("sale_order_poc_drawing.poc_drawing_block", {"poc": poc})
        )
        self.assertIn("<svg", html)
        self.assertRegex(html, r"svg\s*\{\s*width:\s*90mm;\s*height:\s*55mm;")
        self.assertIn("300 mm × 500", html)

    def test_11_the_door_sample_follows_the_opening(self):
        """Образецът „Door — front view“: дръжката е срещу пантите.

        Мутация: в данните посоката `opening` се пренебрегва (винаги ляво).
        """
        door = self.env.ref("sale_order_poc_drawing.drawing_door_front")
        self.assertIn("<svg", str(door.preview))

        def handle_x(opening):
            svg = str(door._render_svg({"width": 900.0, "height": 2000.0, "opening": opening}))
            return float(re.search(r'class="o_poc_door_handle"[^>]*x1="([\d.]+)"', svg).group(1))

        # панти вляво → дръжка вдясно, и обратно
        self.assertGreater(handle_x("left"), 450)
        self.assertLess(handle_x("right"), 450)

    def test_12_only_a_drawing_designer_writes_the_drawing(self):
        """Рисунката на шаблона пише само Drawing Designer (О1); системният я има.

        Мутация: махни проверката в `_poc_drawing_check_access`.
        """
        designer_group = self.env.ref("sale_order_poc_drawing.group_drawing_designer")
        self.assertIn(designer_group, self.env.ref("base.group_system").all_implied_ids)
        self.assertNotIn(designer_group, self.manager.all_group_ids)
        template = self.template.with_user(self.manager)
        # мениджърът пише шаблона, но не и рисунката му
        template.name = "Test Bag 2"
        with self.assertRaises(AccessError):
            template.drawing_defaults = "t_width_mm=1"
        with self.assertRaises(AccessError):
            template.drawing_template_id = False
        with self.assertRaises(AccessError):
            self.drawing.with_user(self.manager).svg = "<svg/>"
        designer = new_test_user(
            self.env,
            login="poc_drawing_designer",
            groups="sales_team.group_sale_manager,"
            "sale_order_poc_drawing.group_drawing_designer",
        )
        self.template.with_user(designer).drawing_defaults = "t_width_mm=5"
        self.drawing.with_user(designer).name = "Rectangle"
        self.assertEqual(self.template.drawing_defaults, "t_width_mm=5")
        # копие на шаблона от мениджъра носи вече одобрената рисунка
        copy = template.copy({"code": "t_bag_copy"})
        self.assertEqual(copy.drawing_template_id, self.drawing)
        # продавачът чете библиотеката
        self.assertTrue(self.drawing.with_user(self.salesman).read(["svg"]))
