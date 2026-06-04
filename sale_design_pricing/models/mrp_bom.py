"""BoM cost engine — recursive walk + vendor pricing + Matrix Template (TM) eval.

Възможности (layer order):

1. **Matrix Template integration** (ако ``bom.matrix_template_id``):
   a. **T1 geometry_table** → enrich params namespace с derived context vars
      (например ``slat_count_mode``, ``caps_mode``, ``terminal_offset``).
      Формулите по bom_lines после виждат тези vars.
   b. **T2 material_table** → coefficient lookup map ``{bom_line_coeff_key:
      coefficient}``. За всеки bom_line, ако има ``matrix_coeff_rule``, qty
      се multiplies с T2 coeff (typically 0 за inactive O-variants, 1.0
      за active). Plus ad-hoc rows които не са в self.bom_line_ids — добавят
      се като extra material lines (например motor install кит).
   c. **T3 operation_table** → conditional workorders (заменят
      self.operation_ids когато TM е active).

2. **Vendor pricing** — material unit cost от ``product.supplierinfo`` с
   min_qty threshold rules чрез ``_select_seller(quantity, uom_id, date,
   partner_id)``. UoM/currency conversion. Fallback на standard_price.

3. **Recursive child BoM walk** (max_depth=10, cycle guard):
   - Phantom child BoM → explode (lines със scaled qty)
   - Semi-finished child BoM → recurse със същите params (parametric
     penetrate в полуфабрикат)
   - Leaf product → vendor pricing
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

_MAX_RECURSION_DEPTH = 10


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _evaluate_cost_with_params(self, params, order_partner=None,
                                    _depth=0, _visited=None):
        """Compute material + labor cost for this BoM given a parameter
        namespace. Recursive за phantom + semi-finished child BoM-и, плюс
        TM activation (T1/T2/T3) ако bom.matrix_template_id is set.

        :param params: flat dict of design params (lot.design_params + lookup
            helpers; виж sale.order.line._build_param_namespace).
        :param order_partner: optional res.partner (SO customer) — passed
            to ``_select_seller`` ако имаш per-customer supplierinfo.

        Returns dict::

            {
                "material_cost": float,
                "labor_cost": float,
                "lines": [{product_id, product_name, qty, unit_cost,
                           subtotal, seller_id, seller_name, price_source,
                           path}, ...],
                "operations": [{workcenter_id, name, minutes, rate_per_hour,
                                subtotal, path}, ...],
                "t0_messages": [{level, message}, ...],   # T0 constraints
                "context_used": dict,                     # final TM ctx
            }
        """
        self.ensure_one()
        if _visited is None:
            _visited = set()
        if self.id in _visited:
            _logger.warning(
                "[sale_design_pricing] BoM cycle at %s — aborting recurse",
                self.display_name,
            )
            return self._empty_cost_result()
        if _depth > _MAX_RECURSION_DEPTH:
            _logger.warning(
                "[sale_design_pricing] BoM recursion depth > %d at %s",
                _MAX_RECURSION_DEPTH, self.display_name,
            )
            return self._empty_cost_result()

        _visited = _visited | {self.id}
        company = self.env.company
        currency = company.currency_id
        today = fields.Date.context_today(self)

        # ── Matrix Template activation (T0/T1/T2/T3) ──────────────────────
        full_ctx = dict(params or {})
        t0_messages = []
        t2_coeff_by_key = {}
        t2_adhoc_rows = []
        t3_operations = None  # None = use self.operation_ids; list = TM-driven

        if self.matrix_template_id:
            t0_messages, full_ctx, t2_coeff_by_key, t2_adhoc_rows, t3_operations \
                = self._tm_evaluate(full_ctx)

        breakdown_lines = []
        breakdown_ops = []
        material_cost = 0.0
        labor_cost = 0.0

        # ── BoM lines (recursive walk + T2 coeff + vendor pricing) ────────
        for bom_line in self.bom_line_ids:
            qty = bom_line._evaluate_quantity(full_ctx)
            # T2 coeff multiplier за O-variants
            coeff = 1.0
            if t2_coeff_by_key and getattr(bom_line, "matrix_coeff_rule", False):
                coeff = float(t2_coeff_by_key.get(bom_line.matrix_coeff_rule, 0.0))
            qty *= coeff
            qty_with_loss = qty * (1.0 + (bom_line.loss or 0.0) / 100.0)
            product = bom_line.product_id
            if not product or qty_with_loss <= 0:
                continue

            child_bom = self._find_child_bom(product, company)

            if child_bom and child_bom.type == "phantom":
                scale = qty_with_loss / (child_bom.product_qty or 1.0)
                child_result = child_bom._evaluate_cost_with_params(
                    full_ctx, order_partner=order_partner,
                    _depth=_depth + 1, _visited=_visited,
                )
                phantom_label = product.display_name
                material_cost += child_result["material_cost"] * scale
                labor_cost += child_result["labor_cost"] * scale
                for ln in child_result["lines"]:
                    breakdown_lines.append({
                        **ln,
                        "qty": ln["qty"] * scale,
                        "subtotal": ln["subtotal"] * scale,
                        "path": [phantom_label] + (ln.get("path") or []),
                    })
                for op in child_result["operations"]:
                    breakdown_ops.append({
                        **op,
                        "subtotal": op["subtotal"] * scale,
                        "path": [phantom_label] + (op.get("path") or []),
                    })
                continue

            if child_bom and child_bom.type == "normal":
                scale = qty_with_loss / (child_bom.product_qty or 1.0)
                child_result = child_bom._evaluate_cost_with_params(
                    full_ctx, order_partner=order_partner,
                    _depth=_depth + 1, _visited=_visited,
                )
                semi_mat = child_result["material_cost"] * scale
                semi_lab = child_result["labor_cost"] * scale
                material_cost += semi_mat
                labor_cost += semi_lab
                semi_label = product.display_name
                breakdown_lines.append({
                    "product_id": product.id,
                    "product_name": semi_label,
                    "qty": qty_with_loss,
                    "unit_cost": ((semi_mat + semi_lab) / qty_with_loss) if qty_with_loss else 0.0,
                    "subtotal": semi_mat + semi_lab,
                    "seller_id": False,
                    "seller_name": "",
                    "price_source": "child_bom",
                    "path": [],
                })
                for ln in child_result["lines"]:
                    breakdown_lines.append({
                        **ln,
                        "qty": ln["qty"] * scale,
                        "subtotal": ln["subtotal"] * scale,
                        "path": [semi_label] + (ln.get("path") or []),
                    })
                for op in child_result["operations"]:
                    breakdown_ops.append({
                        **op,
                        "subtotal": op["subtotal"] * scale,
                        "path": [semi_label] + (op.get("path") or []),
                    })
                continue

            # Leaf product → vendor pricing.
            unit_cost, seller, source = self._resolve_vendor_unit_cost(
                bom_line, qty_with_loss, today, order_partner, currency, company,
            )
            subtotal = qty_with_loss * unit_cost
            material_cost += subtotal
            breakdown_lines.append({
                "product_id": product.id,
                "product_name": product.display_name,
                "qty": qty_with_loss,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "seller_id": seller.id if seller else False,
                "seller_name": seller.partner_id.display_name if seller else "",
                "price_source": source,
                "path": [],
            })

        # ── T2 ad-hoc rows (extra materials NOT bound to a bom_line) ──────
        for row in t2_adhoc_rows:
            product, qty_adhoc, uom = self._resolve_t2_adhoc_row(row, full_ctx)
            if not product or qty_adhoc <= 0:
                continue
            # Mock-ва bom_line за vendor pricing API
            fake_line = self.env["mrp.bom.line"].new({
                "product_id": product.id,
                "product_uom_id": (uom or product.uom_id).id,
                "loss": 0.0,
            })
            unit_cost, seller, source = self._resolve_vendor_unit_cost(
                fake_line, qty_adhoc, today, order_partner, currency, company,
            )
            subtotal = qty_adhoc * unit_cost
            material_cost += subtotal
            breakdown_lines.append({
                "product_id": product.id,
                "product_name": "★ " + product.display_name,  # ★ = T2 ad-hoc
                "qty": qty_adhoc,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "seller_id": seller.id if seller else False,
                "seller_name": seller.partner_id.display_name if seller else "",
                "price_source": source,
                "path": ["T2 ad-hoc"],
            })

        # ── Operations (TM-driven OR local) ───────────────────────────────
        if t3_operations is not None:
            for op_dict in t3_operations:
                wc, minutes = self._resolve_t3_operation(op_dict, full_ctx)
                if not wc:
                    continue
                # Часова ставка = работен център + работник (employee).
                rate = (wc.costs_hour or 0.0) + (wc.employee_costs_hour or 0.0)
                subtotal = (minutes / 60.0) * rate
                labor_cost += subtotal
                breakdown_ops.append({
                    "workcenter_id": wc.id,
                    "name": op_dict.get("name") or wc.display_name,
                    "minutes": minutes,
                    "rate_per_hour": rate,
                    "subtotal": subtotal,
                    "path": ["T3"],
                })
        else:
            for op in self.operation_ids:
                workcenter = op.workcenter_id
                if not workcenter:
                    continue
                minutes = op.time_cycle or 0.0
                rate = (workcenter.costs_hour or 0.0) + (workcenter.employee_costs_hour or 0.0)
                subtotal = (minutes / 60.0) * rate
                labor_cost += subtotal
                breakdown_ops.append({
                    "workcenter_id": workcenter.id,
                    "name": op.name,
                    "minutes": minutes,
                    "rate_per_hour": rate,
                    "subtotal": subtotal,
                    "path": [],
                })

        return {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "lines": breakdown_lines,
            "operations": breakdown_ops,
            "t0_messages": t0_messages,
            "context_used": full_ctx,
        }

    # ── TM evaluation helpers ─────────────────────────────────────────────

    def _tm_evaluate(self, ctx):
        """Извика T0/T1/T2/T3 на matrix template-а (ако bom има такъв).

        :returns: tuple (t0_messages, full_ctx, t2_coeff_by_key,
                  t2_adhoc_rows, t3_operations_or_None).
        """
        from odoo.addons.mrp_design_matrix.models.zen_engine import ZenWrapper

        t0_messages = []
        # T0 constraints — за audit (warnings/errors), не break-ваме pricing
        if self.constraint_table:
            try:
                t0 = ZenWrapper.evaluate(self.constraint_table, ctx)
                rows = t0 if isinstance(t0, list) else (t0 or {}).get("result", [])
                for r in rows:
                    msg = r.get("message")
                    lvl = r.get("level") or "warning"
                    if msg:
                        t0_messages.append({"level": lvl, "message": str(msg)})
            except Exception as e:
                _logger.warning("T0 eval failed on bom %s: %s", self.display_name, e)

        # T1 geometry — derived context vars (slat_count_mode, etc.)
        full_ctx = dict(ctx)
        if self.geometry_table:
            try:
                t1 = ZenWrapper.evaluate(self.geometry_table, ctx)
                rows = t1 if isinstance(t1, list) else (t1 or {}).get("result", [])
                # T1 hitPolicy=first → typically a single row dict
                if isinstance(rows, dict):
                    full_ctx.update({k: v for k, v in rows.items() if v is not None})
                elif rows and isinstance(rows[0], dict):
                    full_ctx.update({k: v for k, v in rows[0].items() if v is not None})
            except Exception as e:
                _logger.warning("T1 eval failed on bom %s: %s", self.display_name, e)

        # T2 materials — coefficient lookup + ad-hoc rows
        t2_coeff_by_key = {}
        t2_adhoc_rows = []
        if self.material_table:
            try:
                t2 = ZenWrapper.evaluate(self.material_table, full_ctx)
                rows = t2 if isinstance(t2, list) else (t2 or {}).get("result", [])
                for r in rows:
                    key = r.get("bom_line_coeff_key")
                    if key:
                        t2_coeff_by_key[key] = float(r.get("coefficient", 0.0))
                    elif r.get("product_ref") or r.get("ptav_id") or r.get("product_id"):
                        t2_adhoc_rows.append(r)
            except Exception as e:
                _logger.warning("T2 eval failed on bom %s: %s", self.display_name, e)

        # T3 operations — conditional workorders
        t3_operations = None
        if self.operation_table:
            try:
                t3 = ZenWrapper.evaluate(self.operation_table, full_ctx)
                t3_operations = t3 if isinstance(t3, list) else (t3 or {}).get("result", [])
            except Exception as e:
                _logger.warning("T3 eval failed on bom %s: %s", self.display_name, e)

        return (t0_messages, full_ctx, t2_coeff_by_key, t2_adhoc_rows, t3_operations)

    def _resolve_t2_adhoc_row(self, row, ctx):
        """Resolve T2 ad-hoc row към (product, qty, uom).

        Поддържани keys (priority order):
        - ``product_ref`` (XMLID) → env.ref()
        - ``ptav_id`` (int) → product.template.attribute.value → product.product
        - ``product_id`` (int) → direct
        Qty: ``quantity`` (default 1.0).
        UoM: ``uom_ref`` (XMLID) → env.ref(), иначе product.uom_id.
        """
        product = False
        qty = float(row.get("quantity", 1.0) or 1.0)
        uom = False
        # XMLID
        if row.get("product_ref"):
            try:
                product = self.env.ref(str(row["product_ref"]).strip("'\""), raise_if_not_found=False)
                if product and product._name == "product.template":
                    product = product.product_variant_id
            except Exception:
                pass
        # PTAV
        if not product and row.get("ptav_id"):
            ptav = self.env["product.template.attribute.value"].browse(int(row["ptav_id"]))
            if ptav.exists():
                # Find first variant съ този PTAV
                product = ptav.product_attribute_value_id.product_ids[:1] or False
        # Direct
        if not product and row.get("product_id"):
            product = self.env["product.product"].browse(int(row["product_id"]))
            if not product.exists():
                product = False
        # UoM
        if row.get("uom_ref"):
            try:
                uom = self.env.ref(str(row["uom_ref"]).strip("'\""), raise_if_not_found=False)
            except Exception:
                pass
        if product and not uom:
            uom = product.uom_id
        return (product, qty, uom)

    def _resolve_t3_operation(self, op_dict, ctx=None):
        """Resolve T3 operation dict към (workcenter, minutes).

        Supported keys:
        - ``workcenter_ref`` (XMLID) → env.ref()
        - ``workcenter_id`` (int) → direct
        Duration: ``duration``/``minutes`` (number) или ``duration_formula``
        (израз, оценен срещу ``ctx`` — напр. ``20 * width/1000 * height/1000``).
        """
        wc = False
        if op_dict.get("workcenter_ref"):
            try:
                wc = self.env.ref(
                    str(op_dict["workcenter_ref"]).strip("'\""),
                    raise_if_not_found=False,
                )
            except Exception:
                pass
        if not wc and op_dict.get("workcenter_id"):
            wc = self.env["mrp.workcenter"].browse(int(op_dict["workcenter_id"]))
            if not wc.exists():
                wc = False
        minutes = float(op_dict.get("duration") or op_dict.get("minutes") or 0.0)
        if not minutes and op_dict.get("duration_formula") is not None:
            minutes = self._eval_t3_duration(op_dict["duration_formula"], ctx or {})
        return (wc, minutes)

    @staticmethod
    def _eval_t3_duration(raw, ctx):
        """T3 duration (minutes): number, numeric string, or a plain-Python
        expression evaluated against ``ctx``.  Plain ``exec`` (not safe_eval —
        safe_eval zeroes such expressions on some builds)."""
        if isinstance(raw, (int, float)):
            return float(raw)
        expr = str(raw or "").strip()
        if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
            expr = expr[1:-1].strip()
        try:
            return float(expr)
        except ValueError:
            pass
        try:
            scope = {"__builtins__": {
                "int": int, "float": float, "min": min, "max": max,
                "round": round, "abs": abs,
            }}
            local = dict(ctx or {})
            exec(compile("__dur__ = " + expr, "<t3_dur>", "exec"), scope, local)
            return float(local.get("__dur__", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0

    def _find_child_bom(self, product, company):
        """Резолва child BoM за продукт (за recursion детекция)."""
        boms = self.env["mrp.bom"]._bom_find(
            products=product, company_id=company.id,
        )
        return boms.get(product) or self.env["mrp.bom"]

    def _resolve_vendor_unit_cost(self, bom_line, qty_with_loss, today,
                                    order_partner, currency, company):
        """Find best vendor price for the given quantity, with UoM/currency
        conversion. Falls back to standard_price.

        :returns: tuple (unit_cost, seller_record_or_False, source_str)
            where source_str is "vendor" or "standard".
        """
        product = bom_line.product_id
        if not product:
            return (0.0, False, "standard")

        seller_kwargs = {
            "quantity": qty_with_loss,
            "uom_id": bom_line.product_uom_id,
            "date": today,
        }
        if order_partner:
            seller_kwargs["partner_id"] = order_partner
        seller = product._select_seller(**seller_kwargs)

        if seller:
            line_uom = bom_line.product_uom_id or product.uom_id
            if seller.product_uom_id and seller.product_uom_id != line_uom:
                price = seller.product_uom_id._compute_price(seller.price, line_uom)
            else:
                price = seller.price
            if seller.currency_id and seller.currency_id != currency:
                price = seller.currency_id._convert(
                    price, currency, company, today,
                )
            return (price, seller, "vendor")

        return (product.standard_price, False, "standard")

    @staticmethod
    def _empty_cost_result():
        return {
            "material_cost": 0.0,
            "labor_cost": 0.0,
            "lines": [],
            "operations": [],
            "t0_messages": [],
            "context_used": {},
        }
