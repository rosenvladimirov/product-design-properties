# MRP Design Matrix — System Requirements Document (SRD)

**Версия:** 1.0 | **Дата:** Март 2026 | **Автор:** Росен Владимиров \<vladimirov.rosen@gmail.com\> | BL Consulting | Odoo Silver Partner

---

## 1. Архитектурен преглед

Системата се реализира като стек от Odoo модули с ясна йерархия на зависимости. Ядрото е generic — индустриалните специфики живеят в отделни субмодули.

| Модул | Тип | Описание |
|---|---|---|
| `mrp_bom_line_formula_quantity` | OCA (съществува) | Формула за количество в BoM ред. |
| `stock_move_forced_lot_multi` | Твой (PR кандидат) | Принудително задаване на лотове на суровинни движения. Propagation до PO. |
| `stock_move_forced_lot_multi_dim` | Субмодул | `width/height/thickness` на `stock.lot`. |
| `mrp_bom_formula_lot_dimension` | **НОВ — мост** | Инжектира lot dims + Properties в formula контекста. ~50 реда. |
| `mrp_design_matrix` | **НОВ — ядро** | Главният модул: дефиниции, шаблони, матрици, MO генерация. |
| `mrp_design_matrix_bags` | Субмодул | Торби за смет. |
| `mrp_design_matrix_corrugated` | Субмодул | Кашони + велпапе. |
| `mrp_design_matrix_roller_door` | Субмодул | Ролетни врати. |
| `mrp_design_matrix_security_door` | Субмодул | Блиндирани врати (RC логика). |
| `mrp_design_matrix_interior_door` | Субмодул | Интериорни врати. |

---

## 2. Модели на данните

### 2.1 `mrp.design.param.definition`

Групира дефиниции на параметри. Аналог на `component.definition.properties` от `product_electrical_properties`.

| Поле | Описание |
|---|---|
| `code` | Уникален код: `'bags'`, `'roller_door'` |
| `name` | Четимо наименование |
| `industry` | Групиране: `'bags'`, `'doors'`, `'corrugated'` |
| `parent_id` | `Many2one → self` (наследяване) |
| `design_params_definition` | `PropertiesDefinition` — схемата на параметрите |

Дефинициите се зареждат от custom XML при инсталация чрез `create_design_param_definitions()`. Форматът следва паттерна на `component_definition.xml`.

### 2.2 `mrp.matrix.template`

Шаблони с правила. Клиентът никога не редактира шаблона директно.

| Поле | Описание |
|---|---|
| `name` | Наименование: `'Торби - стандарт с печат'` |
| `industry` | За филтриране |
| `constraint_table` | `Json` (JSONB) — T0 правила в GoRules формат |
| `geometry_table` | `Json` — T1 правила |
| `material_table` | `Json` — T2 правила |
| `operation_table` | `Json` — T3 правила |

### 2.3 `mrp.bom` (разширен)

| Поле | Описание |
|---|---|
| `design_param_definition_id` | `Many2one → mrp.design.param.definition` |
| `matrix_template_id` | `Many2one → mrp.matrix.template` (само reference) |
| `constraint_table` | `Json` — T0 копие, редактируемо |
| `geometry_table` | `Json` — T1 копие |
| `material_table` | `Json` — T2 копие |
| `operation_table` | `Json` — T3 копие |

### 2.4 `mrp.bom.line` (разширен)

| Поле | Описание |
|---|---|
| `quantity_formula` | `Text` — формула (от OCA модула, съществува) |
| `matrix_coeff_rule` | `Char` — референция към T2 ред за коефициент |
| `coeff_default` | `Float` — `0.0` за O-варианти, `1.0` за реални |
| `product_tmpl_id` | `Many2one → product.template` (за PTAV resolution) |
| `param_attribute_map` | `Json` — `{design_key: attr_external_id}` |
| `param_extraction_map` | `Json` — `{child_key: source_или_формула}` |
| `child_definition_id` | `Many2one → mrp.design.param.definition` |
| `mto_stop` | `Boolean` — спира MTO chain на това ниво |

### 2.5 `stock.lot` (разширен)

| Поле | Описание |
|---|---|
| `width / height / thickness` | `Float` — реални полета (от `_dim` модул) |
| `design_param_definition_id` | `Many2one → mrp.design.param.definition` |
| `design_params` | `Properties` — всички индустриални параметри |
| `bom_id` | `Many2one → mrp.bom` (за context на Properties) |

---

## 3. Design Parameters — Properties Engine

Следва паттерна на `product_electrical_properties`. Параметрите са типизирани, дефинирани чрез XML, съхранявани като JSONB, с автоматично генериран UI.

**Поддържани типове:** `char`, `float`, `boolean`, `selection`.

**Наследяване:** чрез `parent_id` — базовата дефиниция съдържа общи параметри, разширената добавя специфичните.

| Дефиниция | Параметри |
|---|---|
| Торби | `bag_type, has_tie, has_print, density, resin_type, color` |
| Кашони | `board_type, has_print, die_cut` |
| Велпапе | `grammage, flute_type, board_grade` |
| Ролетна врата | `slat_type, drive_type, has_insulation, has_perforation` |
| Блиндирана врата | `RC_class, sheet_thickness, lock_type, has_glass, has_electronic_lock` |
| Интериорна врата | `construction, opening, leaf_type, finish, has_glass_panel, has_soundproof, wall_width` |

### XML формат за дефиниции

```xml
<records>
    <properties code="bags" name="Bags - Standard">
        <items name="bag_type">
            <item name="type">selection</item>
            <item name="selection">[["sleeve","Ръкав"],["sheet","Лист"]]</item>
            <item name="default">sleeve</item>
        </items>
        <items name="has_tie">
            <item name="type">boolean</item>
            <item name="default">false</item>
        </items>
    </properties>
</records>
```

### Четене в Python

```python
design_context = {
    "width":     lot.width,
    "height":    lot.height,
    "thickness": lot.thickness,
    "qty":       production.product_qty,
    **{k: v for k, v in (lot.design_params or {}).items()},
}
# → {"width": 600, "bag_type": "sleeve", "has_tie": True, ...}
```

---

## 4. Матрица — GoRules ZEN Engine

**Библиотека:** `zen-engine` (`pip install zen-engine`). Rust + Python bindings. <1ms latency. Embeddable — без external calls.

Матриците се съхраняват като JSONB в `mrp.bom`. Редактират се чрез `ace_editor` widget в Odoo UI.

### T0 — Ограничения

- Hit policy: `Collect`
- Изпълнява се ПРЕДИ всичко
- `ERROR` → `UserError`, МО не се създава
- `WARNING` → `message_post`, продължава

```
ERROR:   перфорация + has_insulation    (ролетна)
         стъкло + RC_class >= RC4       (блиндирана)
         лист + цепене операция         (торба)

WARNING: width > 4000 + manual          (ролетна)
         solid + width > 900            (интериорна)
```

### T1 — Геометрия

- Hit policy: `Unique`
- Три типа ефекти:
  - `context_modify` — изчислява intermediate var (`effective_length`)
  - `context_force` — override с минимум (`sheet_thickness = max(user, RC_min[RC_class])`)
  - `context_derive` — от физика (`motor_class = f(area × slat_weight_per_m2)`)
- Изходът обогатява `full_context` за T2, T3 и formula модула

### T2 — Материали

- Hit policy: `Collect (sum)`
- **Тип 1 — O-variant activation:** `{"bom_line_coeff_key": "...", "coefficient": 1.15}`
- **Тип 2 — Direct ref:** `{"product_ref": "module.product_xmlid", "quantity": "...", ...}`
- **Тип 3 — PTAV resolution:** `{"product_tmpl_ref": "...", "param_attribute_map": {"color": "module.attr_color"}, ...}`

### T3 — Операции

- Hit policy: `Any`
- Условно добавя workorders
- Изход: `{"workcenter_ref": "...", "duration_formula": "...", "sequence": int}`

---

## 5. PTAV Resolution

Design параметър → `product.attribute` → `product.attribute.value` → `product.product` variant.

```
design_params.color = "FF0000"
    ↓ param_attribute_map: {"color": "module.attr_color"}
attribute: Color / value: "FF0000"
    ↓ _get_variant_for_combination(ptav)
product.product: Мастило + Color/FF0000
```

**Изискване:** стойностите на `design_params` трябва да съответстват точно на `product.attribute.value.name`.

```python
def _resolve_variant_by_ptav(self, tmpl, param_attr_map, design_ctx):
    needed_ptav = self.env["product.template.attribute.value"]
    for param_key, attr_ref in param_attr_map.items():
        value = design_ctx.get(param_key)
        if value is None:
            continue
        attribute = self.env.ref(attr_ref)
        ptav = self.env["product.template.attribute.value"].search([
            ("product_tmpl_id", "=", tmpl.id),
            ("attribute_id",    "=", attribute.id),
            ("name",            "=", str(value)),
        ], limit=1)
        if ptav:
            needed_ptav |= ptav
    return tmpl._get_variant_for_combination(needed_ptav)
```

---

## 6. Полуфабрикати — рекурсивна верига

```
Краен продукт lot_1: {bag_type, has_tie, width, color, thickness}
    МО Level 1
        ├── Фолио (полуфабрикат)
        │       lot_2: {bag_type, width, color, thickness}
        │       ← param_extraction_map от BoM линията
        │       МО Level 2 → смола (mto_stop=True → PO)
        │
        └── Връзка
                lot_3: {tie_length: height+50}
                ← трансформация чрез safe_eval
                mto_stop=True → PO или stock
```

### param_extraction_map формат

```json
{
  "bag_type":   "bag_type",
  "width":      "width",
  "tie_length": "height + 50"
}
```

Прост ключ → директно копие. Израз → `safe_eval` срещу parent lot context.

### MTO Stop логика

| `mto_stop` | Действие |
|---|---|
| `False` | Създава нов МО + `_create_child_lot()` |
| `True` | `_find_matching_lot()` от stock → ако няма → PO с параметрите |

---

## 7. Конструиране на МО — алгоритъм

```python
def _generate_design_matrix_moves(self):
    bom = self.bom_id
    if not bom.constraint_table:
        return  # стандартен BoM

    lot = self.lot_producing_id
    ctx = {
        "width": lot.width, "height": lot.height,
        "thickness": lot.thickness, "qty": self.product_qty,
        **{k: v for k, v in (lot.design_params or {}).items()},
    }

    # T0 — constraints
    t0 = engine.create_decision(bom.constraint_table).evaluate(ctx)
    for e in t0.get("errors", []):
        raise UserError(_("Design constraint: %s") % e["message"])
    for w in t0.get("warnings", []):
        self.message_post(body=_("Warning: %s") % w["message"])

    # T1 — geometry (forced values override user input)
    t1 = engine.create_decision(bom.geometry_table).evaluate(ctx)
    full_ctx = {**ctx, **t1}

    # T2 — BoM lines × (formula × coeff) [Тип 1: O-variants]
    for line in bom.bom_line_ids:
        qty_base = line._eval_quantity_formula(..., context=full_ctx)
        coeff = self._eval_matrix_coeff(line, full_ctx)
        if qty_base * coeff > 0.0:
            self._create_matrix_move_raw(line.product_id, qty_base * coeff, ...)

    # T2 — ad-hoc [Тип 2: direct / Тип 3: PTAV]
    for item in engine.create_decision(bom.material_table).evaluate(full_ctx).get("result", []):
        if item.get("coefficient", 0.0) > 0.0:
            product = self._resolve_t2_product(item, full_ctx)
            self._create_matrix_move_raw(product, ...)

    # T3 — operations
    for op in engine.create_decision(bom.operation_table).evaluate(full_ctx).get("result", []):
        self._create_matrix_workorder(self.env.ref(op["workcenter_ref"]), op)

    # Semi-finished: child lots + mto_stop
    for move in self.move_raw_ids.filtered(lambda m: m.bom_line_id.child_definition_id):
        line = move.bom_line_id
        if line.mto_stop:
            match = self._find_matching_lot(move.product_id, ...)
            if match:
                move.forced_lot_ids = [(4, match.id)]
        else:
            child_lot = self._create_child_lot(lot, line)
            move.forced_lot_ids = [(4, child_lot.id)]
```

---

## 8. Структура на repo

```
mrp_design_matrix/
    models/
        mrp_design_param_definition.py
        mrp_matrix_template.py
        mrp_bom.py
        mrp_bom_line.py
        mrp_production.py
        stock_lot.py
    views/
        mrp_bom_views.xml           ← таб "Design Matrix" + ace_editor
        mrp_matrix_template_views.xml
        mrp_design_param_definition_views.xml
    data/
        base_param_definitions.xml

mrp_design_matrix_{industry}/
    data/
        design_param_definitions.xml
        install_design_params.xml
        matrix_templates/
            {name}.json
    demo/
        demo_bom_{industry}.xml
```

---

## 9. OCA изисквания

- Лиценз: AGPL-3
- Зависимости само от OCA/Odoo CE
- `zen-engine` в `external_dependencies`
- Тестове: поне един на функционалност
- Pre-commit: `ruff`, `black`, OCA checks
- Towncrier changelog
- `README.rst` с DESCRIPTION, USAGE, CONFIGURE
