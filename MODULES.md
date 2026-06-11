# Модулен каталог — product-design-properties

Този repo съдържа **22 модула** организирани в 6 архитектурни слоя.
Цел: параметрично производство (make-to-order) в Odoo 18 — design params
върху lot-ове, DMN-style rule matrix върху BoM, configurator с 3D preview
върху sale order line.

---

## Архитектурни слоеве

```
┌─────────────────────────────────────────────────────────────┐
│ Customer-specific (Teolino)                                  │
│   teolino_mrp_design_recompute  teolino_sale_design_*_ui     │
├─────────────────────────────────────────────────────────────┤
│ Sale-side UX                                                 │
│   sale_design_configurator  sale_design_pricing              │
├─────────────────────────────────────────────────────────────┤
│ Industry parameter sets (9 модула)                           │
│   mrp_design_matrix_bags  …_interior_door  …_shutters       │
├─────────────────────────────────────────────────────────────┤
│ Matrix engine                                                │
│   mrp_design_matrix                                          │
├─────────────────────────────────────────────────────────────┤
│ Formula authoring (опционално)                               │
│   mrp_bom_line_formula_template  …_wizard  …_claude          │
├─────────────────────────────────────────────────────────────┤
│ Foundation / data layer                                      │
│   design_param_base  product_design_assets  stock_lot_props  │
└─────────────────────────────────────────────────────────────┘
```

---

## Foundation / data layer

| Модул | v | Какво прави |
|---|---|---|
| **`design_param_base`** | 18.0.1.1.1 | `design.param.definition` модел — споделени параметри (Width/Height/Color/Material/...) с типове, selection values, SVG профили. Foundation за всички останали слоеве. |
| **`product_design_assets`** | 18.0.1.1.0 | Свързва 3D assets (GLB), SVG profiles, PNG textures към продукти през ir.attachment. Захранва 3D preview-то в configurator-а. |
| **`stock_lot_properties`** | 18.0.1.0.0 | `stock.lot` получава `design_params` JSON поле, привързано към `design.param.definition`. Лотът става "snapshot" на конфигурацията на конкретно изделие. |

---

## Matrix engine

| Модул | v | Какво прави |
|---|---|---|
| **`mrp_design_matrix`** | 18.0.2.0.0 | Сърцето. `mrp.matrix.template` с 8 декларативни DMN таблици (T0/T1/T2/T3/TΦ/TΠ/TΛ/TΩ) за пълно покриване на параметричен BoM. `zen.decision.table` + `zen.decision.log` (Odoo 19-style models за versioned decision graphs, runtime през `zen-engine` Python lib). |

**8-те нива:**

| Таблица | Роля |
|---|---|
| **T0** `constraint_table` | Валидационни правила преди MO creation (ERROR/WARNING, hitPolicy collect) |
| **T1** `geometry_table` | Per-model offsets/forced values (intermediate context vars, hitPolicy first) |
| **T2** `material_table` | O-variant activation, coefficients (hitPolicy collect) |
| **T3** `operation_table` | Conditional workorders (hitPolicy collect) |
| **TΦ** `cascade_table` | Value propagation (lookup() expressions, only_if_empty флаг) |
| **TΠ** `availability_table` | Reactive UI control (visible/enabled/allowed_values/default_override) |
| **TΛ** `layout_table` | Declarative UX (section, widget_hint, customer_visible) |
| **TΩ** `multiplicity_table` | Multi-instance metadata (count_param, per_instance_params, aggregator) |

---

## Industry parameter sets

Всеки depend-ва само на `mrp_design_matrix`; добавя `design.param.definition` + `mrp.matrix.template` records за конкретен продуктов клас. Drop-in модули.

| Модул | v | За кого |
|---|---|---|
| **`mrp_design_matrix_shutters`** | 18.0.1.6.0 | **Щори** — пълна 8-таблична матрица за 5 модела (Standard / Round / T-Roll / Built-In / Thermo Comfort). Включва lookup_tables (box_by_height). Reference implementation. |
| **`mrp_design_matrix_roller_door`** | 18.0.1.5.0 | Ролетни врати (рулонни) |
| **`mrp_design_matrix_roller_garage_door`** | 18.0.1.0.0 | Гаражни ролетни |
| **`mrp_design_matrix_interior_door`** | 18.0.1.0.0 | Вътрешни врати |
| **`mrp_design_matrix_security_door`** | 18.0.1.0.0 | Брониранни врати (с RC class логика) |
| **`mrp_design_matrix_smart_display`** | 18.0.1.0.0 | Smart home display panels |
| **`mrp_design_matrix_corrugated`** | 18.0.1.1.0 | Картонени опаковки |
| **`mrp_design_matrix_bags`** | 18.0.1.0.0 | Найлонови чанти |
| **`mrp_design_matrix_canned_peppers`** | 18.0.1.0.0 | Консервирани печени чушки (food-industry демо) |

---

## Formula authoring (BoM line quantity formulas)

| Модул | v | Какво прави |
|---|---|---|
| **`mrp_bom_line_formula_template`** | 18.0.1.3.0 | Reusable templates за `quantity_formula` на BoM lines (например slat_count formula multi-shutter). |
| **`mrp_bom_line_formula_wizard`** | 18.0.1.1.0 | UI wizard за editing formula-и с syntax помощ. |
| **`mrp_bom_line_formula_claude`** | 18.0.1.0.0 | Claude AI assistant — генерира формули през MCP terminal интеграция (depends на `l10n_bg_claude_terminal`). |

---

## Sale-side UX

| Модул | v | Какво прави |
|---|---|---|
| **`sale_design_configurator`** | 18.0.1.11.0 | OWL/Three.js front-end. Modal върху SO line с param controls + 3D preview (GLB loader, SVG profile, или legacy `_buildShutter/_buildInteriorDoor/...` builders). Eval-ва T0/T1/TΠ/TΦ rules реактивно. Запазва lot със `design_params` JSON. |
| **`sale_design_pricing`** | 18.0.1.2.1 | Cost-plus pricing — отделни material vs labor markups върху параметрични продукти. |

---

## Customer-specific (Teolino)

| Модул | v | Какво прави |
|---|---|---|
| **`teolino_mrp_design_recompute`** | 18.0.1.2.1 | (1) Live `bom.simulate_with_params()` engine — взима design_params + per-shutter pairs → връща `{lines: [{bom_line_id, qty}], total_material}`. (2) `action_confirm` override автоматично recompute-ва raw move qty на MO. (3) `teolino_report_data()` за cut-list QWeb report. |
| **`teolino_sale_design_configurator_ui`** | 18.0.1.8.4 | Per-model UX shenanigans — model filtering, constraint visibility, LIVE BoM preview панел, per-component color sub-modal (`TeolinoColorDialog`). |

---

## Independent

| Модул | v | Какво прави |
|---|---|---|
| **`access_control`** | 18.0.1.0.0 | Полиморфен physical access control: subjects, perimeters, control points, ZEN-driven decision flow с offline sync. Reuse-ва `mrp_design_matrix` engine за rule definitions, но в съвсем различен домейн (HR attendance / access). |

---

## Типичен installation flow

За **щори (Teolino)**:

```
design_param_base, stock_lot_properties, product_design_assets   ← foundation
  └─ mrp_design_matrix                                            ← engine
       └─ mrp_design_matrix_shutters                      ← param + matrix data
  └─ sale_design_configurator                                     ← front-end
       └─ sale_design_pricing                                     ← markup
       └─ teolino_mrp_design_recompute                            ← live BoM simulate
            └─ teolino_sale_design_configurator_ui                ← Teolino UX overrides
```

За **нова индустрия** (напр. PVC прозорци):
1. Създай `mrp_design_matrix_pvc_windows` (depend само на `mrp_design_matrix`)
2. Дефинирай `design.param.definition` records (width/height/color/profile_system/...)
3. Дефинирай `mrp.matrix.template` запис със попълнени T0–TΩ декларативни таблици
4. Optional: добави `_buildPvcWindow()` 3D widget в `sale_design_configurator` за non-GLB preview

---

## Версионни branches

- `18.0` — текуща production за Teolino
- `19.0` — порт в `~/Проекти/odoo/odoo-19.0/product-design-properties/`. Engine е почти идентичен; sale_design_configurator JS-ът използва същия OWL код. Mатериалните модули са copied-as-is + manifest version bump.

---

## Свързани зависимости (extern)

- **`stock_move_forced_lot_multi`** (OCA fork; `~/Проекти/odoo/odoo-18.0/manufacture/`) — изисква се от `mrp_design_matrix` за parent-child orderpoint per lot
- ~~`mrp_bom_line_formula_quantity`~~ — вече НЕ се изисква; formula evaluation е собствено ядро в `mrp_bom_line_formula_template`
- **`zen-engine`** (PyPI ≥0.50) — runtime decision evaluator за `zen.decision.table`

---

## Git remote

`git@github.com:rosenvladimirov/product-design-properties.git`

Push към `origin/18.0` за production fix-ове, `origin/19.0` за паралелните 19.0 ports.
