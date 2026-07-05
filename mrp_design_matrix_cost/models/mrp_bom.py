# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
import logging

from odoo import _, api, fields, models
from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _ensure_design_cost_access(self):
        """Достъп до пари (себестойност/маржин/продажна) — само мениджъри.

        Групата досега пазеше само UI бутона; методите бяха отворени по RPC за
        всеки логнат потребител (sales/design). Server-side gate = каноничният.
        su bypass: вътрешни server флоу-та (репорти през sudo, -u loader).
        """
        if self.env.su or self.env.user._is_admin():
            return
        if not self.env.user.has_group(
            "mrp_design_matrix_cost.group_design_manager"
        ):
            raise AccessError(
                _("Only Design / Manager (Cost) users can access cost data.")
            )

    # Брат на variant_context_map, но чете ОБИКНОВЕНИ Odoo полета в контекста
    # (не атрибути). Само ЧЕТЕ — матрицата не променя стойностите (напр. цената
    # идва от ценоразписа/продукта; тук само я внасяме за справка/сверка).
    field_context_map = fields.Json(
        "Field → Context Map",
        help="Maps design context keys to Odoo field paths read (read-only) "
        "from the product template, e.g. {\"sale_price\": \"list_price\"}. "
        "Used to pull the standard price into the cost preview WITHOUT changing "
        "it — the pricelist/SO line remains the source of truth.",
    )

    # ── Field link (read-only) ───────────────────────────────────────────
    def _get_field_context_values(self, record=None):
        """Чете полетата по field_context_map от *record* (или продукта)."""
        self.ensure_one()
        fmap = self.field_context_map or {}
        if not fmap:
            return {}
        source = record or self.product_tmpl_id
        result = {}
        for ctx_key, field_path in fmap.items():
            try:
                val = source.mapped(field_path)
                result[ctx_key] = val[0] if val else None
            except Exception as exc:  # noqa: BLE001 — линкът е екстра
                _logger.warning("field_context_map %s=%r: %s", ctx_key, field_path, exc)
                result[ctx_key] = None
        return result

    # ── Последна покупна цена (енжин от purchase_order_line_price_history,
    # БЕЗ зависимост към модула и БЕЗ визуализация — само извличане) ──────
    def _last_po_price(self, product):
        """Последната единична цена, на която продуктът е КУПУВАН по поръчка.
        Същата логика като purchase.order.line.price.history (product +
        потвърдена/приключена поръчка), сведена само до извличане на цената.
        Подредба по id (най-новият ред = последна покупка; date_order е related
        non-stored → не е безопасен за order=). 0.0 ако няма покупки."""
        if not product:
            return 0.0
        line = self.env["purchase.order.line"].sudo().search(
            [("product_id", "=", product.id),
             ("order_id.state", "in", ["purchase", "done"])],
            order="id desc", limit=1,
        )
        return line.price_unit or 0.0

    # ── Ценоразписна отстъпка (Теолино патърн) ────────────────────────────
    def _design_pricelist_discount(self, product, pricelist, qty=1.0):
        """% отстъпка от ценоразписа за продукта (приложимо percentage
        правило, по специфичност: вариант → шаблон → категория → глобал).
        0.0 ако няма. Само ЧЕТЕ — не пипа цени."""
        if not pricelist or not product:
            return 0.0
        tmpl = product.product_tmpl_id
        today = fields.Date.context_today(self)
        Item = self.env["product.pricelist.item"].sudo()
        base = [
            ("pricelist_id", "=", pricelist.id),
            ("compute_price", "=", "percentage"),
            ("min_quantity", "<=", qty or 1.0),
        ]
        domains = [
            base + [("applied_on", "=", "0_product_variant"),
                    ("product_id", "=", product.id)],
            base + [("applied_on", "=", "1_product"),
                    ("product_tmpl_id", "=", tmpl.id)],
        ]
        if product.categ_id:
            domains.append(
                base + [("applied_on", "=", "2_product_category"),
                        ("categ_id", "child_of", product.categ_id.id)])
        domains.append(base + [("applied_on", "=", "3_global")])
        for dom in domains:
            for it in Item.search(dom, order="min_quantity desc"):
                if it.date_start and it.date_start > today:
                    continue
                if it.date_end and it.date_end < today:
                    continue
                return it.percent_price or 0.0
        return 0.0

    # ── Sentinel (D2): дневна проверка на еталонна конфигурация ──────────
    SENTINEL_PARAM = "mrp_design_matrix_cost.sentinel_checks"

    @api.model
    def _cron_design_cost_sentinel(self):
        """Дневен канарче-тест: симулира еталонни конфигурации и АЛАРМИРА
        при отклонение (activity към Design/Manager + chatter на BoM-а).

        Щеше да хване T3=[] инцидента ден 1 (труд→0 = под допуска + счупен
        инвариант), вместо да се открива на око в оферта. Конфигурация в
        ir.config_parameter SENTINEL_PARAM (JSON):
        [{"bom_id": 36, "context": {...}, "expect_total": 627.04,
          "tolerance_pct": 20, "min_material": 1.0, "min_labor": 1.0,
          "min_operations": 1}]
        """
        import json as _json
        raw = self.env["ir.config_parameter"].sudo().get_param(
            self.SENTINEL_PARAM, "")
        if not raw:
            return
        try:
            checks = _json.loads(raw)
        except (TypeError, ValueError):
            _logger.error("cost sentinel: invalid JSON in %s",
                          self.SENTINEL_PARAM)
            return
        for chk in checks or []:
            bom = self.sudo().browse(int(chk.get("bom_id", 0)))
            if not bom.exists():
                self._sentinel_alert(
                    bom, "Sentinel BoM %s not found" % chk.get("bom_id"))
                continue
            try:
                res = bom.simulate_design_cost(chk.get("context") or {}, 1.0)
            except Exception as exc:  # noqa: BLE001
                self._sentinel_alert(bom, "simulate crashed: %s" % exc)
                continue
            problems = []
            if res.get("incomplete"):
                problems.append("cost incomplete: %s" % res.get("error"))
            if res.get("total_material", 0.0) < (chk.get("min_material") or 0):
                problems.append("material %.2f < min %.2f"
                                % (res.get("total_material", 0.0),
                                   chk["min_material"]))
            if res.get("total_labor", 0.0) < (chk.get("min_labor") or 0):
                problems.append("labor %.2f < min %.2f (T3 silent-empty?)"
                                % (res.get("total_labor", 0.0),
                                   chk["min_labor"]))
            if len(res.get("operations") or []) < (
                    chk.get("min_operations") or 0):
                problems.append("operations %d < min %d"
                                % (len(res.get("operations") or []),
                                   chk["min_operations"]))
            expect = chk.get("expect_total")
            tol = (chk.get("tolerance_pct") or 20.0) / 100.0
            total = res.get("total_cost", 0.0)
            if expect and not (expect * (1 - tol) <= total <= expect * (1 + tol)):
                problems.append(
                    "total %.2f outside %.2f ±%.0f%%"
                    % (total, expect, tol * 100))
            if problems:
                self._sentinel_alert(
                    bom, "Design cost sentinel FAILED for %s:\n- %s"
                    % (bom.display_name, "\n- ".join(problems)))
            else:
                _logger.info("cost sentinel OK for BoM %s (total %.2f)",
                             bom.id, total)

    def _sentinel_alert(self, bom, message):
        """Alarm канал: log.error + chatter + activity към мениджърите."""
        _logger.error("COST SENTINEL: %s", message)
        if not bom or not bom.exists():
            return
        try:
            bom.message_post(body=message)
            group = self.env.ref("mrp_design_matrix_cost.group_design_manager",
                                 raise_if_not_found=False)
            users = group.user_ids if group else self.env["res.users"]
            for user in users.filtered(lambda u: u.active)[:5]:
                self.env["mail.activity"].sudo().create({
                    "res_model_id": self.env["ir.model"]._get_id("mrp.bom"),
                    "res_id": bom.id,
                    "activity_type_id": self.env.ref(
                        "mail.mail_activity_data_warning").id,
                    "user_id": user.id,
                    "summary": "Design cost sentinel alert",
                    "note": message.replace("\n", "<br/>"),
                })
        except Exception as exc:  # noqa: BLE001 — алармата не бива да чупи cron-а
            _logger.error("cost sentinel alert delivery failed: %s", exc)

    @api.model
    def simulate_cost_for_product(self, product_id, design_context=None,
                                  product_uom_qty=1.0, lot_id=False):
        """Динамичен cost preview по ЖИВИЯ design контекст (от конфигуратора),
        без записан лот. Намира BoM по продукт и извиква simulate_design_cost.
        Ако е подаден lot_id → реалната продажна се чете от свързания SO ред
        (price_unit от ценоразписа). Само ЧЕТЕ.

        Достъп: методът е ЖИВАТА калкулация на конфигуратора и тече и на sales
        ниво (не само cost) → не режем достъпа твърдо. Вместо това:
        - portal/public → AccessError (само вътрешни потребители);
        - мениджър (group_design_manager) → пълен отговор;
        - друг вътрешен (sales) → REDACTED: само продажната част (sale_*,
          currency), БЕЗ себестойност/маржин (lines/operations/totals).
        Преди: пълната себестойност беше достъпна за всеки логнат по RPC."""
        if not self.env.user._is_internal():
            raise AccessError(
                _("Only internal users can access the design configurator.")
            )
        is_manager = (self.env.user._is_admin()
                      or self.env.user.has_group(
                          "mrp_design_matrix_cost.group_design_manager"))
        # sale_actual=False (не None) — None чупи чист xmlrpc marshal.
        empty = {
            "lines": [], "operations": [],
            "sale_suggested": 0.0, "sale_actual": False, "currency_id": False,
        }
        if is_manager:
            empty.update(total_material=0.0, total_labor=0.0, total_cost=0.0)
        else:
            empty["redacted"] = True  # и error пътищата са redacted за sales
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return dict(empty, error="No product")
        bom = self.sudo()._bom_find(product).get(product)
        if not bom:
            return dict(empty, error="No BoM for product")
        sale_record = None
        if lot_id:
            sale_record = self.env["sale.order.line"].sudo().search(
                [("design_lot_id", "=", lot_id)], limit=1
            ) or None
        # sudo: вътрешният simulate_design_cost има твърд мениджърски gate;
        # тук достъпът се управлява от redact-а по-долу. env.company остава
        # на викащия → цените се четат по неговата фирма (както досега).
        res = bom.sudo().simulate_design_cost(
            design_context or {}, product_uom_qty, sale_record=sale_record
        )
        if is_manager:
            return res
        # REDACT за не-мениджъри: само продажната част, без cost breakdown.
        # error/incomplete пътуват (D2): продавачът трябва да ЗНАЕ, че цената
        # е непълна — не да оферира по грешна сума.
        return {
            "redacted": True,
            "sale_suggested": res.get("sale_suggested", 0.0),
            "sale_suggested_net": res.get("sale_suggested_net", 0.0),
            "pricelist_discount": res.get("pricelist_discount", 0.0),
            "sale_actual": res.get("sale_actual", False),
            "currency_id": res.get("currency_id", False),
            "incomplete": res.get("incomplete", False),
            "error": res.get("error", False),
            "lines": [],
            "operations": [],
        }

    # ── Parametric cost roll-up (Теолино патърн, върху Solid матрицата) ───
    def simulate_design_cost(self, design_context=None, product_uom_qty=1.0, sale_record=None, _depth=0):
        """Себестойност (материали + труд) по design контекста, + предложена
        продажна (markup) и реална продажна (read през field_context_map).

        Само ЧЕТЕ — не създава движения, не пипа цени. Защитно (try/except),
        за да не чупи UI-а при липсващи таблици/формули.
        """
        self.ensure_one()
        if not _depth:  # рекурсията (sub-BOM) е вече проверена на дълбочина 0
            self._ensure_design_cost_access()
        # D2: eval грешките НЕ се гълтат тихо — събират се и пътуват в
        # резултата (errors/incomplete) → UI-ът показва „цената е непълна"
        # вместо правдоподобно-грешна сума (T3=[] класа инциденти).
        eval_errors = []
        ctx = dict(design_context or {})
        ctx.setdefault("qty", product_uom_qty)

        # T1 geometry (ако има)
        full_ctx = dict(ctx)
        if self.geometry_table:
            try:
                t1 = ZenWrapper.evaluate(self.geometry_table, ctx)
                if isinstance(t1, dict):
                    full_ctx.update(t1)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("cost T1 eval failed: %s", exc)
                eval_errors.append("T1 geometry: %s" % exc)

        # T2 coeffs (ако има)
        coeff_by_key = {}
        if self.material_table:
            try:
                raw = ZenWrapper.evaluate(self.material_table, full_ctx)
                rows = raw if isinstance(raw, list) else raw.get("result", [])
                for item in rows:
                    key = item.get("bom_line_coeff_key")
                    if key:
                        coeff_by_key[key] = float(item.get("coefficient", 0.0))
            except Exception as exc:  # noqa: BLE001
                _logger.warning("cost T2 eval failed: %s", exc)
                eval_errors.append("T2 materials: %s" % exc)

        # ── Материали ────────────────────────────────────────────────────
        empty_mo = self.env["mrp.production"]
        out_lines = []
        total_material = 0.0
        extra_products = []
        for line in self.bom_line_ids:
            qty = line.product_qty
            product = line.product_id
            if line.quantity_formula:
                try:
                    res = line._eval_quantity_formula(
                        line.product_id, line.product_uom_id,
                        product_uom_qty, empty_mo, design_context=full_ctx,
                    )
                    if isinstance(res, dict):
                        qty = res.get("quantity", qty)
                        if res.get("product"):
                            product = res["product"]
                        # add_products (kit канала): допълнителните
                        # (product, qty) се ценят след цикъла — MO потокът
                        # ги консумира в _create_formula_extra_move, cost
                        # трябва да ги вижда със същия контракт
                        extra_products += res.get("add_products") or []
                    elif res is not None:
                        qty = res
                except Exception as exc:  # noqa: BLE001
                    _logger.warning("cost formula eval (line %s): %s", line.id, exc)
                    eval_errors.append(
                        "formula (%s): %s" % (line.product_id.display_name, exc))
            # material_choice: ако конфигураторът е подал избор (choice_<key>),
            # цени реалния вариант, а не placeholder-а (иначе Обков/Брава и др.
            # остават 0). Същата резолюция като production._resolve_material_choice.
            if line.material_choice_ids:
                ckey = line.matrix_coeff_rule or ("line%d" % line.id)
                cval = full_ctx.get("choice_%s" % ckey)
                if cval:
                    try:
                        cpid = int(cval)
                    except (TypeError, ValueError):
                        cpid = None
                    if cpid:
                        chosen = line.material_choice_ids.filtered(
                            lambda p: p.id == cpid)
                        if chosen:
                            product = chosen[:1]
            coeff = 1.0
            if line.matrix_coeff_rule and line.matrix_coeff_rule in coeff_by_key:
                coeff = coeff_by_key[line.matrix_coeff_rule]
            qty_final = (qty or 0.0) * coeff
            # Фира (loss): реалната консумация и цена включват отпадъка
            # (Теолино патърн) → qty_with_loss = qty * (1 + loss).
            qty_with_loss = qty_final * (1.0 + (line.loss or 0.0))
            # Sub-BOM roll-up: ако компонентът е сборка със собствен BoM
            # (крило/каса), цената за 1 бр = рекурсивната себестойност на този
            # BoM, не плоския standard_price. Защита от цикъл чрез _depth.
            sub_bom = False
            if _depth < 5 and product:
                sub_bom = self.env["mrp.bom"].sudo()._bom_find(product).get(product)
            if sub_bom and sub_bom.id != self.id:
                sub = sub_bom.simulate_design_cost(
                    full_ctx, 1.0, _depth=_depth + 1)
                unit_cost = sub.get("total_cost", 0.0)
                price_source = "BoM"
                if sub.get("errors"):
                    eval_errors += ["%s → %s" % (product.display_name, e)
                                    for e in sub["errors"]]
            else:
                # Себестойност: standard_price; ако е 0 → последна покупна цена
                # (енжин като purchase_order_line_price_history), маркирана „(ПО)".
                unit_cost = product.standard_price or 0.0
                price_source = ""
                if not unit_cost:
                    po_price = self._last_po_price(product)
                    if po_price:
                        unit_cost = po_price
                        price_source = "ПО"
            subtotal = qty_with_loss * unit_cost
            total_material += subtotal
            display_name = product.display_name
            if price_source:
                display_name = "%s (%s)" % (display_name, price_source)
            out_lines.append({
                "product_id": product.id,
                "product_name": display_name,
                "qty": qty_with_loss,
                "loss": line.loss or 0.0,
                "uom": line.product_uom_id.name,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "price_source": price_source,
            })

        # ── add_products (динамични kit компоненти) ──────────────────────
        # Контрактът на mrp_bom_line_formula_template: [{product|ref,
        # quantity[, uom]}]. Без loss/coeff — правилата дават крайното
        # количество. Markup-ът остава консистентен: смята се от
        # total_material накрая.
        for item in extra_products:
            try:
                eprod = item.get("product")
                if not eprod and item.get("ref"):
                    eprod = self.env.ref(item["ref"], raise_if_not_found=False)
                if eprod is not None and eprod._name == "product.template":
                    eprod = eprod.product_variant_id
                if not eprod:
                    continue
                eqty = item.get("quantity", 0.0)
                if isinstance(eqty, str):
                    from odoo.tools.safe_eval import safe_eval as _se
                    eqty = _se(eqty, dict(full_ctx))
                eqty = float(eqty or 0.0)
            except Exception as exc:  # noqa: BLE001
                eval_errors.append("add_products: %s" % exc)
                continue
            if eqty <= 0:
                continue
            unit_cost = eprod.standard_price or 0.0
            price_source = ""
            if not unit_cost:
                po_price = self._last_po_price(eprod)
                if po_price:
                    unit_cost = po_price
                    price_source = "ПО"
            subtotal = eqty * unit_cost
            total_material += subtotal
            display_name = eprod.display_name
            if price_source:
                display_name = "%s (%s)" % (display_name, price_source)
            out_lines.append({
                "product_id": eprod.id,
                "product_name": display_name,
                "qty": eqty,
                "loss": 0.0,
                "uom": eprod.uom_id.name,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "price_source": price_source,
            })

        # ── Труд (T3) — best-effort ──────────────────────────────────────
        operations = []
        total_labor = 0.0
        if self.operation_table:
            try:
                t3 = ZenWrapper.evaluate(self.operation_table, full_ctx)
                ops = t3 if isinstance(t3, list) else t3.get("result", [])
                if not ops:
                    # тих 0-труд капан: T3 има правила условни на height>0; ако контекстът
                    # няма 'height' (или геометрията смени ключа) → 0 операции без грешка.
                    _logger.info("cost T3: 0 операции (height=%r) → труд=0.",
                                 full_ctx.get("height"))
                for op in ops:
                    # T3 връща workcenter_code (не xmlid) + duration_min → намери
                    # workcenter по code (беше workcenter_ref/env.ref → винаги None).
                    # ZEN връща output-а като string literal с кавички ('"SDMILL"') → strip.
                    code = op.get("workcenter_code") or op.get("workcenter_ref")
                    if isinstance(code, str):
                        code = code.strip().strip('"').strip("'").strip()
                    # sudo: работните центрове са фирмено-специфични (SDMETAL е на
                    # Продакшън, останалите на Солид 55) и НЕ могат да се споделят
                    # (resource company constraint каскадира към календари) → четем rate-а
                    # независимо от активната фирма, за да е трудът unified като материала.
                    # Това е симулация (read-only) → sudo е безопасно.
                    wc = (self.env["mrp.workcenter"].sudo().search([("code", "=", code)], limit=1)
                          if code else None)
                    minutes = float(op.get("duration_min") or op.get("duration")
                                    or op.get("minutes") or 0.0)
                    if not wc or minutes <= 0:
                        continue
                    rate = (wc.costs_hour or 0.0) + (getattr(wc, "employee_costs_hour", 0.0) or 0.0)
                    cost = (minutes / 60.0) * rate
                    total_labor += cost
                    operations.append({
                        "name": str(op.get("name") or wc.name),
                        "workcenter": wc.name,
                        "minutes": round(minutes, 1),
                        "rate": rate,
                        "cost": cost,
                    })
            except Exception as exc:  # noqa: BLE001
                _logger.warning("cost T3 eval failed: %s", exc)
                eval_errors.append("T3 operations: %s" % exc)

        # ── Продажна: предложена (markup) + реална (read от ценоразписа) ──
        tmpl = self.product_tmpl_id
        mat_mk = (tmpl.material_markup_percent or 0.0) / 100.0
        lab_mk = (tmpl.labor_markup_percent or 0.0) / 100.0
        sale_suggested = total_material * (1.0 + mat_mk) + total_labor * (1.0 + lab_mk)

        field_ctx = self._get_field_context_values(record=sale_record)
        # False (не None) при липсваща реална продажна — None чупи xmlrpc clients
        # (cannot marshal None) и не носи повече инфо от falsy.
        sale_actual = field_ctx.get("sale_price")
        if sale_actual is None:
            sale_actual = False

        # ── Ценоразписна отстъпка (Теолино патърн): % от приложимото
        # percentage правило (вариант→шаблон→категория→глобал). Прилага се
        # върху предложената цена → sale_suggested_net (нетна предложена). ──
        pricelist_discount = 0.0
        if sale_record and sale_record._name == "sale.order.line":
            pricelist_discount = self._design_pricelist_discount(
                sale_record.product_id,
                sale_record.order_id.pricelist_id,
                sale_record.product_uom_qty or 1.0,
            )
        sale_suggested_net = sale_suggested * (1.0 - pricelist_discount / 100.0)

        total_cost = total_material + total_labor
        result_error = ("Cost is INCOMPLETE: " + "; ".join(eval_errors)
                        if eval_errors else False)
        return {
            "errors": eval_errors,
            "incomplete": bool(eval_errors),
            "error": result_error,
            "lines": out_lines,
            "total_material": total_material,
            "operations": operations,
            "total_labor": total_labor,
            "total_cost": total_cost,
            "sale_suggested": sale_suggested,
            "pricelist_discount": pricelist_discount,
            "sale_suggested_net": sale_suggested_net,
            "sale_actual": sale_actual,
            # споделеният BoM 36 е company_id=False → self.company_id е празен recordset и
            # .currency_id.id би върнал False. Fallback към активната фирма → реалната валута.
            "currency_id": (self.company_id or self.env.company).currency_id.id,
        }

