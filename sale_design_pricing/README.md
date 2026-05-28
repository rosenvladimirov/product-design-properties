# sale_design_pricing — How it works

**Цел:** на SO line с параметричен продукт (linked to a `stock.lot` с
`design_params`) изчислява **material + labor cost** + **markups** → крайна
**list price**. Hooks в `_get_display_price()` за да заменя стандартния
pricelist lookup.

---

## Архитектура (data flow)

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  SO Line                                                          │
   │  ▸ product_id (parametric template)                               │
   │  ▸ design_lot_id  ──► stock.lot.design_params (JSON, per-instance) │
   └──────────────────────────┬───────────────────────────────────────┘
                              │
              _build_param_namespace()
                              │ flatten lot.design_params:
                              │   {hashed_name: value, label: value,
                              │    snake_label: value}
                              ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  mrp.bom._evaluate_cost_with_params(params)                       │
   │                                                                   │
   │  for line in self.bom_line_ids:                                   │
   │     qty = line._evaluate_quantity(params)   ← safe_eval formula  │
   │     qty *= (1 + loss/100)                                         │
   │     subtotal = qty * standard_price                               │
   │  → material_cost (Σ)                                              │
   │                                                                   │
   │  for op in self.operation_ids:                                    │
   │     hours = time_cycle / 60                                       │
   │     subtotal = hours * workcenter.costs_hour                      │
   │  → labor_cost (Σ)                                                 │
   │                                                                   │
   │  → {material_cost, labor_cost, lines[], operations[]}             │
   └──────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  product.template.effective_*_markup_percent                      │
   │  fallback chain:                                                  │
   │     tmpl.design_*_markup_percent                                  │
   │       ⤷ categ_id.design_*_markup_percent                          │
   │           ⤷ company_id.design_*_markup_percent                    │
   └──────────────────────────┬───────────────────────────────────────┘
                              │ ×(1 + markup/100)
                              ▼
              list_price_material + list_price_labor
                              │
                              ▼
                      list_price_total
                              │
            _get_display_price() override
                              │
                              ▼
                   SO line price_unit / subtotal
```

---

## Компоненти

### `sale.order.line` (`models/sale_order_line.py`)

| Поле | Тип | Произход |
|---|---|---|
| `cost_material` | Float | Σ от `bom_line.qty × loss × standard_price` |
| `cost_labor` | Float | Σ от `operation.time_cycle × workcenter.costs_hour` |
| `list_price_material` | Float | `cost_material × (1 + mat_markup)` |
| `list_price_labor` | Float | `cost_labor × (1 + lab_markup)` |
| `list_price_total` | Float | `list_price_material + list_price_labor` |
| `cost_breakdown_html` | Html | Table с per-line/per-op breakdown (за preview в SO line) |

**Recompute trigger** — `@api.depends("design_lot_id", "design_lot_id.design_params", "product_id", "...markup_percent")`. Веднага щом lot params се променят, цялото pricing се преcalculates.

**Display price hook** — `_get_display_price()` override returns `list_price_total` ако lot има design_params + product е параметричен. Иначе fallback на стандартния Odoo pricelist lookup (super()).

### `mrp.bom` (`models/mrp_bom.py`)

`_evaluate_cost_with_params(params) → dict`:
- Iterates `self.bom_line_ids` → `_evaluate_quantity(params)` (per line)
- Multiplies by `(1 + loss/100)` за waste/loss factor
- `unit_cost = product.standard_price`
- Iterates `self.operation_ids` → `(time_cycle / 60) × workcenter.costs_hour`
- Returns structured `{material_cost, labor_cost, lines[], operations[]}` — used от SO line + HTML breakdown.

### `mrp.bom.line` (`models/mrp_bom_line.py`)

`_evaluate_quantity(params) → float`:
- Чете `self.quantity_formula` (текст поле, typically multi-line `try/except` block)
- `safe_eval(formula, globals_dict={**params, **_FORMULA_EXCEPTIONS}, mode='exec')`
- Чете `quantity` (или `result`) от namespace-а след execution
- Fallback на `self.product_qty` ако формула липсва ИЛИ eval-ът гръмне (с warning лог)

**Защо `mode='exec'` не `'eval'`:** формулите обикновено са `try: quantity = ...
except: quantity = product_qty` блок → не може с single expression. Exception класовете (Exception, ValueError, TypeError, ZeroDivisionError, KeyError, AttributeError) се инжектират в namespace-а защото safe_eval ги изключва по default.

**Пример формула** (от typical shutter BoM line):
```python
try:
    n = int(slat_count_mode_formula(height, box_size, slat_size))
    quantity = n * (width / 1000)
except Exception:
    quantity = product_qty
```

### `product.template` (`models/product_template.py`)

Markup fallback chain:
| Stage | Стойност |
|---|---|
| 1 | `tmpl.design_material_markup_percent` (per-product override) |
| 2 | `tmpl.categ_id.design_material_markup_percent` (per-category default) |
| 3 | `tmpl.company_id.design_material_markup_percent` (company default) |

(Same chain за labor). Computed като `effective_material_markup_percent` / `effective_labor_markup_percent`.

### `stock.lot` (`models/stock_lot.py`)

Понастоящем placeholder — никакви reusable полета. Customer-specific extensions (като Teolino's `teolino_per_shutter_dims`) живеят в customer override модули (`teolino_mrp_design_recompute`).

### `res.company` + `product.category` (`models/res_company.py`, `product_category.py`)

Идентични полета `design_material_markup_percent` и `design_labor_markup_percent` — служат като fallback levels (виж product.template chain).

---

## Параметрите → формула пътя

```
stock.lot.design_params  (JSONB на storage)
   │
   │ [{"name": "8a3c...", "value": "standard",
   │   "string": "Shutter Model", "type": "selection",
   │   "selection": [["standard","Standard"], ...]}, ...]
   │
   ▼ lot.read(["design_params"])
   ▼ flatten → ns dict:
   │   ns["8a3c..."] = "standard"           ← hashed name (storage key)
   │   ns["Shutter Model"] = "standard"     ← human label
   │   ns["shutter_model"] = "standard"     ← snake_case
   │
   ▼ mrp.bom.line.quantity_formula:
       try:
           if shutter_model == "thermo_comfort":
               quantity = (width + 70) / 1000
           else:
               quantity = (width + 55) / 1000
       except Exception:
           quantity = product_qty
```

Формулата може да реферира параметъра по която и да е от 3-те имена. Snake_case формата е препоръчителна — четима и stable.

---

## Hooks за customer overrides

При нужда от customer-specific логика (напр. multi-shutter aggregation,
description rendering, BoM line condition):

1. **`mrp.bom._evaluate_cost_with_params`** — override-вай в customer модул за добавяне на per-instance loop (виж `teolino_mrp_design_recompute.mrp_bom.simulate_with_params` за паралелен method който eval-ва per panel).

2. **`mrp.bom.line._evaluate_quantity`** — override-вай ако формулите ти изискват extra helpers в namespace-а (например `lookup_table()` достъп до TΦ cascade tables).

3. **`sale.order.line._compute_design_pricing`** — replace ако искаш custom pricing strategy (например volume discounts на ниво SO total).

4. **`sale.order.line.set_design_lot`** — override за post-lot hooks (например `_teolino_refresh_design_description` в `teolino_mrp_design_recompute.sale_order_line`).

---

## Координация с други модули

| Module | Какво internalint-ва | Когато |
|---|---|---|
| `mrp_design_matrix` | T2 material_table казва coefficient × line.qty (O-variants); T3 operation_table казва кой workorder да се прибави с какъв time. | Когато BoM-ът има `matrix_template_id` set. _evaluate_cost_with_params изпълнява само текущите bom_line_ids/operation_ids — TM activation се случва ПО ВРЕМЕ на confirm (через _teolino_recompute_raw_moves), не тук. |
| `teolino_mrp_design_recompute` | `mrp.bom.simulate_with_params()` — паралелен engine който прави per-shutter loop + връща `{lines: [{bom_line_id, qty}], total_material}`. Customer-side replacement на `_evaluate_cost_with_params` за multi-panel quoting. | Override-ва pricing engine когато multi-shutter (TΩ multiplicity) е активен. |
| `mrp_bom_line_formula_template` | Reusable templates за `quantity_formula` — не tu, но source-ите на формулите. | When user wants prebuilt formulas (slat_count, axis_length и др.) |

---

## Implemented (v18.0.1.3+)

1. ✅ **Vendor pricing** — `_select_seller(quantity, uom_id, date, partner_id)` с min_qty rules + UoM/currency conversion. Fallback на standard_price.
2. ✅ **Recursive BoM walk** — phantom (explode) + semi-finished (recurse със same params). Max depth 10, cycle guard.
3. ✅ **Matrix Template (T0-T3) integration** когато `bom.matrix_template_id` is set:
   - T0 → audit messages (showing като alert banners в HTML breakdown)
   - T1 → enrich params namespace с derived context vars
   - T2 → coefficient lookup (per `matrix_coeff_rule`) + ad-hoc product rows (XMLID/PTAV/direct id)
   - T3 → conditional workorders (заменя self.operation_ids)
4. ✅ **Per-customer pricing** — SO `order_id.partner_id` → `_select_seller` за customer-specific supplierinfo.

## Граници (оставащи)

1. **`time_cycle` от T3** — duration се чете директно. Ако TM rule връща formula expression (не number), не се evaluate-ва. Бъдещо: support `safe_eval` за T3 duration string.
2. **Loss factor** — фиксиран на ниво BoM line. Conditional waste по design params (TM rule-driven loss) не се прилага.
3. **TΩ Multiplicity** — multi-instance loop (например per-shutter eval) не е integrate-нат в pricing engine. Тoзи job-а е override-нат от `teolino_mrp_design_recompute.mrp_bom.simulate_with_params` за Teolino.
