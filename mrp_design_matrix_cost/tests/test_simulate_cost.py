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
"""Тестове на ФИНАНСОВИЯ engine (D2: доверие в числата).

Голдън тестове на simulate_design_cost/simulate_cost_for_product: материален
roll-up (qty × standard_price + фира), sub-BOM рекурсия, труд (T3 × ставка,
zen-guard), markup → предложена продажна, redact/gate достъпът, error
агрегацията (incomplete вместо тихо-грешна цена), currency fallback.
Fixtures са индустриално-НЕУТРАЛНИ (продукт/BoM без врати-специфика) —
същият engine ще носи щори/каси/чанти.
"""
from unittest import skipUnless

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from odoo.addons.base_zen_decision.models.zen_engine import _ZEN_AVAILABLE


def _t3_graph(rules):
    """Минимален ВАЛИДЕН JDM граф (T3 формат: workcenter_code+duration_min)."""
    return {
        "nodes": [
            {"id": "in1", "type": "inputNode", "name": "Request"},
            {"id": "dt1", "type": "decisionTableNode", "name": "T3",
             "content": {
                 "hitPolicy": "collect",
                 "inputs": [{"id": "h", "name": "height", "field": "height"}],
                 "outputs": [
                     {"id": "wc", "name": "workcenter_code",
                      "field": "workcenter_code"},
                     {"id": "dur", "name": "duration_min",
                      "field": "duration_min"},
                 ],
                 "rules": rules,
             }},
            {"id": "out1", "type": "outputNode", "name": "Response"},
        ],
        "edges": [
            {"id": "e1", "sourceId": "in1", "targetId": "dt1"},
            {"id": "e2", "sourceId": "dt1", "targetId": "out1"},
        ],
    }


class TestSimulateDesignCost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.uom_unit = env.ref("uom.product_uom_unit")

        def product(name, price, route_manufacture=False):
            tmpl = env["product.template"].create({
                "name": name,
                "type": "consu",
                "standard_price": price,
            })
            return tmpl.product_variant_id

        # компоненти
        cls.comp_a = product("D2 Sheet", 10.0)
        cls.comp_b = product("D2 Handle", 25.0)
        cls.comp_sub = product("D2 Leaf (semi-finished)", 0.0)
        cls.comp_sub_raw = product("D2 Leaf raw", 40.0)

        # sub-BOM: Leaf = 2 × Leaf raw (40) → 80
        cls.sub_bom = env["mrp.bom"].create({
            "product_tmpl_id": cls.comp_sub.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
            "bom_line_ids": [(0, 0, {
                "product_id": cls.comp_sub_raw.id,
                "product_qty": 2.0,
            })],
        })

        # главен продукт + markup (материал 10%, труд 50%)
        cls.final = product("D2 Final Door-ish Thing", 0.0)
        cls.final.product_tmpl_id.write({
            "material_markup_percent": 10.0,
            "labor_markup_percent": 50.0,
        })
        # главен BoM: 3×A(10) + 1×B(25, loss 20%) + 1×sub(→80)
        cls.bom = env["mrp.bom"].create({
            "product_tmpl_id": cls.final.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.comp_a.id, "product_qty": 3.0}),
                (0, 0, {"product_id": cls.comp_b.id, "product_qty": 1.0,
                        "loss": 0.2}),
                (0, 0, {"product_id": cls.comp_sub.id, "product_qty": 1.0}),
            ],
        })

        # работен център за труда
        cls.wc = env["mrp.workcenter"].create({
            "name": "D2 Assembly", "code": "D2ASM", "costs_hour": 60.0,
        })

        # потребители: мениджър / вътрешен (sales) / portal
        cls.user_manager = env["res.users"].create({
            "name": "D2 Manager", "login": "d2_manager",
            "group_ids": [(6, 0, [
                env.ref("base.group_user").id,
                env.ref("mrp_design_matrix_cost.group_design_manager").id,
            ])],
        })
        cls.user_sales = env["res.users"].create({
            "name": "D2 Sales", "login": "d2_sales",
            "group_ids": [(6, 0, [env.ref("base.group_user").id])],
        })
        cls.user_portal = env["res.users"].create({
            "name": "D2 Portal", "login": "d2_portal",
            "group_ids": [(6, 0, [env.ref("base.group_portal").id])],
        })

    # ── материален roll-up ────────────────────────────────────────────────
    def test_material_rollup_with_loss_and_subbom(self):
        res = self.bom.simulate_design_cost({}, 1.0)
        # A: 3×10=30 · B: 1×(1+0.2)×25=30 · sub: 1×(2×40)=80 → 140
        self.assertAlmostEqual(res["total_material"], 140.0, places=2)
        self.assertFalse(res["incomplete"])
        by_name = {ln["product_name"]: ln for ln in res["lines"]}
        sub_line = next(v for k, v in by_name.items() if "Leaf (semi" in k)
        self.assertEqual(sub_line["price_source"], "BoM")
        self.assertAlmostEqual(sub_line["unit_cost"], 80.0, places=2)

    def test_markup_sale_suggested(self):
        res = self.bom.simulate_design_cost({}, 1.0)
        # без труд: 140 × 1.10 = 154
        self.assertAlmostEqual(res["sale_suggested"], 154.0, places=2)

    def test_currency_fallback_shared_bom(self):
        # споделен BoM (company_id=False) → валутата на активната фирма
        self.bom.company_id = False
        res = self.bom.simulate_design_cost({}, 1.0)
        self.assertEqual(res["currency_id"], self.env.company.currency_id.id)

    # ── труд (T3) ─────────────────────────────────────────────────────────
    @skipUnless(_ZEN_AVAILABLE, "zen-engine not installed")
    def test_labor_from_t3(self):
        self.bom.operation_table = _t3_graph([
            {"_id": "r1", "h": "> 0", "wc": '"D2ASM"', "dur": "30"},
        ])
        res = self.bom.simulate_design_cost({"height": 2000}, 1.0)
        # 30 мин × 60 €/ч = 30
        self.assertAlmostEqual(res["total_labor"], 30.0, places=2)
        self.assertEqual(len(res["operations"]), 1)
        self.assertAlmostEqual(res["total_cost"], 170.0, places=2)
        # markup: 140×1.1 + 30×1.5 = 154 + 45 = 199
        self.assertAlmostEqual(res["sale_suggested"], 199.0, places=2)

    @skipUnless(_ZEN_AVAILABLE, "zen-engine not installed")
    def test_labor_zero_when_no_rule_matches(self):
        self.bom.operation_table = _t3_graph([
            {"_id": "r1", "h": "> 9000", "wc": '"D2ASM"', "dur": "30"},
        ])
        res = self.bom.simulate_design_cost({"height": 2000}, 1.0)
        self.assertEqual(res["total_labor"], 0.0)
        self.assertEqual(res["operations"], [])

    # ── error агрегация (D2: без тихо-грешни цени) ───────────────────────
    def test_formula_error_marks_incomplete(self):
        line = self.bom.bom_line_ids[0]
        if "quantity_formula" not in line._fields:
            self.skipTest("formula module not installed")
        # директен write в кеша (без validation на формулата)
        line.with_context(skip_formula_validation=True).quantity_formula = \
            "quantity = 1 / 0"
        res = self.bom.simulate_design_cost({}, 1.0)
        self.assertTrue(res["incomplete"])
        self.assertTrue(res["errors"])
        self.assertIn("INCOMPLETE", res["error"])

    # ── достъп: gate + redact ─────────────────────────────────────────────
    def test_gate_direct_simulate_denied_for_non_manager(self):
        with self.assertRaises(AccessError):
            self.bom.with_user(self.user_sales).simulate_design_cost({}, 1.0)

    def test_manager_gets_full_response(self):
        res = self.env["mrp.bom"].with_user(
            self.user_manager).simulate_cost_for_product(self.final.id, {})
        self.assertIn("total_cost", res)
        self.assertNotIn("redacted", res)
        self.assertAlmostEqual(res["total_material"], 140.0, places=2)

    def test_sales_gets_redacted_response(self):
        res = self.env["mrp.bom"].with_user(
            self.user_sales).simulate_cost_for_product(self.final.id, {})
        self.assertTrue(res.get("redacted"))
        self.assertNotIn("total_cost", res)
        self.assertNotIn("total_material", res)
        self.assertAlmostEqual(res["sale_suggested"], 154.0, places=2)
        self.assertEqual(res["lines"], [])

    def test_portal_denied(self):
        with self.assertRaises(AccessError):
            self.env["mrp.bom"].with_user(
                self.user_portal).simulate_cost_for_product(self.final.id, {})

    def test_loader_gated(self):
        # load_ksi_bom живее в solid_door (D1) — не е dependency на cost;
        # gate-тестът важи само когато клиентският модул е инсталиран.
        if not hasattr(self.env["mrp.bom"], "load_ksi_bom"):
            self.skipTest("mrp_design_matrix_solid_door not installed")
        with self.assertRaises(AccessError):
            self.env["mrp.bom"].with_user(self.user_sales).load_ksi_bom(
                "mrp_design_matrix_solid_door", "ksi_bom_data.json")

    # ── sentinel ──────────────────────────────────────────────────────────
    def test_sentinel_alerts_on_low_labor(self):
        import json
        self.env["ir.config_parameter"].sudo().set_param(
            self.env["mrp.bom"].SENTINEL_PARAM,
            json.dumps([{"bom_id": self.bom.id, "context": {},
                         "min_labor": 5.0}]))
        before = self.env["mail.message"].search_count(
            [("model", "=", "mrp.bom"), ("res_id", "=", self.bom.id)])
        self.env["mrp.bom"]._cron_design_cost_sentinel()
        after = self.env["mail.message"].search_count(
            [("model", "=", "mrp.bom"), ("res_id", "=", self.bom.id)])
        self.assertGreater(after, before,
                           "sentinel must post an alert on the BoM chatter")

    def test_sentinel_quiet_when_ok(self):
        import json
        self.env["ir.config_parameter"].sudo().set_param(
            self.env["mrp.bom"].SENTINEL_PARAM,
            json.dumps([{"bom_id": self.bom.id, "context": {},
                         "expect_total": 140.0, "tolerance_pct": 5,
                         "min_material": 1.0}]))
        before = self.env["mail.message"].search_count(
            [("model", "=", "mrp.bom"), ("res_id", "=", self.bom.id)])
        self.env["mrp.bom"]._cron_design_cost_sentinel()
        after = self.env["mail.message"].search_count(
            [("model", "=", "mrp.bom"), ("res_id", "=", self.bom.id)])
        self.assertEqual(after, before, "no alert expected when within bounds")
