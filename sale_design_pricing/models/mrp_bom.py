from odoo import models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _evaluate_cost_with_params(self, params):
        """Compute material + labor cost for this BoM given a parameter namespace.

        Returns a dict::

            {
                "material_cost": float,
                "labor_cost": float,
                "lines": [{"product_id", "product_name", "qty", "unit_cost", "subtotal"}, ...],
                "operations": [{"workcenter_id", "name", "minutes", "rate_per_hour", "subtotal"}, ...],
            }

        ``params`` is a flat dict of design parameters (lot.design_params merged
        with template-level design properties).
        """
        self.ensure_one()
        breakdown_lines = []
        material_cost = 0.0
        for bom_line in self.bom_line_ids:
            qty = bom_line._evaluate_quantity(params)
            qty_with_loss = qty * (1.0 + (bom_line.loss or 0.0) / 100.0)
            unit_cost = bom_line.product_id.standard_price
            subtotal = qty_with_loss * unit_cost
            material_cost += subtotal
            breakdown_lines.append({
                "product_id": bom_line.product_id.id,
                "product_name": bom_line.product_id.display_name,
                "qty": qty_with_loss,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
            })

        breakdown_ops = []
        labor_cost = 0.0
        for op in self.operation_ids:
            workcenter = op.workcenter_id
            if not workcenter:
                continue
            minutes = op.time_cycle or 0.0
            rate = workcenter.costs_hour or 0.0
            subtotal = (minutes / 60.0) * rate
            labor_cost += subtotal
            breakdown_ops.append({
                "workcenter_id": workcenter.id,
                "name": op.name,
                "minutes": minutes,
                "rate_per_hour": rate,
                "subtotal": subtotal,
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
