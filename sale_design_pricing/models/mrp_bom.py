"""BoM cost engine — recursive walk на BoM tree + vendor pricing.

Възможности:
1. **Vendor pricing** — material unit cost се извлича от
   ``product.supplierinfo`` (vendor pricelist) с min_qty threshold rules
   чрез ``product._select_seller(quantity=qty_with_loss, ...)``. Fallback
   на ``standard_price`` ако няма seller.

2. **Recursive child BoM walk**:
   - **Phantom child BoM** (``type='phantom'``) — explode-ва се: добавят
     се child bom_line-ите със scaled qty (replace на phantom-product line).
     Не consume-ва labor (phantom не държи operations за production).
   - **Semi-finished child BoM** (``type='normal'``) — recurse-ва: child-ът
     се eval-ва с **същите** design params (parametric параметрите се
     propagate-ват в полуфабрикат-а). Cost-ът на полуфабрикат-а става
     SUM(child_material) + SUM(child_labor). Spawn-натите material lines
     наследяват от parent breakdown с marker.
   - **Без child BoM** (leaf product) — vendor pricing.

3. **Recursion guard** — max_depth=10 prевентира безкрайни loops в случай
   на циклични BoM-и (рядко, но reportable).

Output dict от phantom/recurse е same shape както от leaf — lines/operations
arrays могат свободно да се accumulate-ват от parent.
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
        namespace. Recursive за phantom + semi-finished child BoM-и.

        :param params: flat dict of design params (lot.design_params merged
            с template-level design properties).
        :param order_partner: optional res.partner (SO customer) — passed
            to ``_select_seller`` ако имаш per-customer supplierinfo.
        :param _depth: internal recursion counter (max=10).
        :param _visited: set от BoM IDs вече visited (cycle guard).

        Returns dict::

            {
                "material_cost": float,
                "labor_cost": float,
                "lines": [{"product_id", "product_name", "qty", "unit_cost",
                           "subtotal", "seller_id", "seller_name",
                           "price_source", "path"}, ...],
                "operations": [{"workcenter_id", "name", "minutes",
                                "rate_per_hour", "subtotal", "path"}, ...],
            }

        ``price_source`` ∈ {"vendor", "standard", "child_bom"}
        ``path`` — list of parent-product display names за phantom/semi
        traceability (празен list за top-level lines).
        """
        self.ensure_one()
        if _visited is None:
            _visited = set()
        if self.id in _visited:
            _logger.warning(
                "[sale_design_pricing] BoM cycle detected at %s — aborting recurse",
                self.display_name,
            )
            return {"material_cost": 0.0, "labor_cost": 0.0,
                    "lines": [], "operations": []}
        if _depth > _MAX_RECURSION_DEPTH:
            _logger.warning(
                "[sale_design_pricing] BoM recursion depth > %d at %s",
                _MAX_RECURSION_DEPTH, self.display_name,
            )
            return {"material_cost": 0.0, "labor_cost": 0.0,
                    "lines": [], "operations": []}

        _visited = _visited | {self.id}
        company = self.env.company
        currency = company.currency_id
        today = fields.Date.context_today(self)

        breakdown_lines = []
        breakdown_ops = []
        material_cost = 0.0
        labor_cost = 0.0

        for bom_line in self.bom_line_ids:
            qty = bom_line._evaluate_quantity(params)
            qty_with_loss = qty * (1.0 + (bom_line.loss or 0.0) / 100.0)
            product = bom_line.product_id
            if not product or qty_with_loss <= 0:
                continue

            # Look up child BoM за този product (phantom или normal).
            child_bom = self._find_child_bom(product, company)

            if child_bom and child_bom.type == "phantom":
                # Phantom: explode-ва се. Child-ът връща материалите с
                # scaled qty; phantom-product line НЕ се добавя в breakdown.
                scale = qty_with_loss / (child_bom.product_qty or 1.0)
                child_result = child_bom._evaluate_cost_with_params(
                    params, order_partner=order_partner,
                    _depth=_depth + 1, _visited=_visited,
                )
                phantom_label = product.display_name
                material_cost += child_result["material_cost"] * scale
                # phantom не вика operations (по конвенция) но ако child_bom
                # има — accumulate-ваме ги също.
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
                # Semi-finished: recurse със същите params (parametric
                # параметрите се propagate-ват в полуфабрикат-а).
                scale = qty_with_loss / (child_bom.product_qty or 1.0)
                child_result = child_bom._evaluate_cost_with_params(
                    params, order_partner=order_partner,
                    _depth=_depth + 1, _visited=_visited,
                )
                semi_mat = child_result["material_cost"] * scale
                semi_lab = child_result["labor_cost"] * scale
                material_cost += semi_mat
                labor_cost += semi_lab
                semi_label = product.display_name
                # Една обобщена линия за полуфабрикат-а (audit-friendly).
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
                # Plus детайл — child lines/operations с path prefix
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

            # Leaf product — vendor pricing.
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

        # Local operations на текущия BoM.
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
                "path": [],
            })

        return {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "lines": breakdown_lines,
            "operations": breakdown_ops,
        }

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

        # Native Odoo: returns best supplierinfo по (sequence, price, min_qty,
        # date_start/end). Respects partner_id ако е подадено, иначе fallback.
        seller_kwargs = {
            "quantity": qty_with_loss,
            "uom_id": bom_line.product_uom_id,
            "date": today,
        }
        if order_partner:
            seller_kwargs["partner_id"] = order_partner
        seller = product._select_seller(**seller_kwargs)

        if seller:
            # Supplierinfo.price е в seller.product_uom_id (uom от вендорската
            # оферта, например `Pack of 100`). Конвертирай в BoM line UoM.
            line_uom = bom_line.product_uom_id or product.uom_id
            if seller.product_uom_id and seller.product_uom_id != line_uom:
                price = seller.product_uom_id._compute_price(seller.price, line_uom)
            else:
                price = seller.price
            # Currency conversion ако supplier е в друга валута.
            if seller.currency_id and seller.currency_id != currency:
                price = seller.currency_id._convert(
                    price, currency, company, today,
                )
            return (price, seller, "vendor")

        # Fallback: internal cost ако product няма supplier.
        return (product.standard_price, False, "standard")
