# MRP Design Matrix — Project Plan

**Версия:** 1.0 | **Дата:** Март 2026 | **Автор:** BL Consulting | Odoo Silver Partner

---

## Обхват и цел

Разработване и публикуване в OCA на стек от Odoo 18 модули за design-driven manufacturing. Проектът включва ядрото (generic engine) и пет индустриални субмодула.

**Краен резултат:** PR в `OCA/manufacture` и `OCA/stock-logistics-workflow`.

**Обща продължителност:** ~11 седмици

---

## Фаза 0 — Основа (2 седмици)

Подготовка на съществуващите модули за OCA публикуване.

| Задача | Модул | Приоритет | Усилие |
|---|---|---|---|
| PR: `stock_move_forced_lot_multi` | stock-logistics-workflow | Критичен | 3 дни |
| PR: `stock_move_forced_lot_multi_dim` | stock-logistics-workflow | Критичен | 1 ден |
| Тестове за forced lot propagation | горните | Критичен | 2 дни |
| OCA pre-commit setup за новото repo | `mrp_design_matrix` | Висок | 0.5 дни |

**Ключов резултат:** forced_lot PR-овете в OCA — всичко останало зависи от тях.

---

## Фаза 1 — Мостът (1 седмица)

`mrp_bom_formula_lot_dimension` — критичният модул от който зависи цялата formula логика.

| Задача | Описание | Усилие |
|---|---|---|
| `_quantity_formula_values` override | Добавя lot dims и Properties flatten в контекста | 1 ден |
| Тестове | Formula използва `width` и `bag_type` от lot Properties | 1 ден |
| README + changelog | OCA стандарт | 0.5 дни |

**Ключов резултат:** `quantity_formula` вижда всички design_params без допълнителен код.

---

## Фаза 2 — Ядро: модели (2 седмици)

| Задача | Описание | Усилие |
|---|---|---|
| `mrp.design.param.definition` | PropertiesDefinition + XML парсер | 2 дни |
| `mrp.matrix.template` | 4× Json полета, базов CRUD | 1 ден |
| `mrp.bom` разширение | `design_param_definition_id`, 4× Json, `action_load_from_template()` | 2 дни |
| `mrp.bom.line` разширение | `coeff_default`, `matrix_coeff_rule`, `param_attribute_map`, `param_extraction_map`, `child_definition_id`, `mto_stop` | 2 дни |
| `stock.lot` разширение | `design_param_definition_id` + `design_params` Properties | 1 ден |
| `ace_editor` widget | JSON редактор в BoM форм за 4-те таблици | 2 дни |

**Ключов резултат:** всички модели са налице, UI позволява конфигурация на матриците.

---

## Фаза 3 — Ядро: логика (2 седмици)

| Задача | Описание | Усилие |
|---|---|---|
| GoRules wrapper клас | Зарежда JSONB, `evaluate()`, error handling | 1 ден |
| `_generate_design_matrix_moves()` | T0/T1 chain, основния алгоритъм | 3 дни |
| `_resolve_t2_product()` | Тип 1/2/3 dispatch | 1 ден |
| `_resolve_variant_by_ptav()` | PTAV matching логика | 2 дни |
| `_create_child_lot()` | `param_extraction_map` с копие и `safe_eval` | 2 дни |
| `_find_matching_lot()` | Stock matching по `design_params` | 1 ден |
| `mto_stop` логика | Разклонение в `_generate_design_matrix_moves` | 1 ден |
| Интеграционни тестове | Поне 5 теста покриващи основните пътища | 3 дни |

**Ключов резултат:** пълен MO алгоритъм работи end-to-end с тестове.

---

## Фаза 4 — Индустриални субмодули (3 седмици)

| Субмодул | XML дефиниции | JSON шаблони | Тестове | Усилие |
|---|---|---|---|---|
| `mrp_design_matrix_bags` | `bag_type, has_tie, density...` | standard, with_print | 2 | 3 дни |
| `mrp_design_matrix_corrugated` | `board_type, grammage...` | BC standard, single wall | 2 | 3 дни |
| `mrp_design_matrix_roller_door` | `slat_type, drive_type...` | manual, electric | 2 | 4 дни |
| `mrp_design_matrix_security_door` | `RC_class, sheet_thickness...` | RC2, RC3, RC4 | 3 | 4 дни |
| `mrp_design_matrix_interior_door` | `construction, opening...` | HDF standard, solid premium | 2 | 3 дни |

**Ключов резултат:** всеки субмодул инсталируем, с demo данни и работещи шаблони.

---

## Фаза 5 — Финализация и OCA (1 седмица)

| Задача | Описание | Усилие |
|---|---|---|
| Code review и cleanup | `ruff`, `black`, OCA checks — нула грешки | 2 дни |
| Документация | `README.rst` за всеки модул | 2 дни |
| PR submission | `OCA/manufacture` + `OCA/stock-logistics-workflow` | 1 ден |
| Demo данни | `demo_bom_*.xml` за всеки субмодул | 1 ден |

---

## Обобщена времева линия

| Фаза | Продължителност | Ключов резултат |
|---|---|---|
| Фаза 0 — Основа | 2 седмици | forced_lot PR в OCA |
| Фаза 1 — Мост | 1 седмица | formula модулът вижда Properties |
| Фаза 2 — Модели | 2 седмици | Всички модели + UI |
| Фаза 3 — Логика | 2 седмици | Пълен MO алгоритъм |
| Фаза 4 — Субмодули | 3 седмици | 5 индустриални пакета |
| Фаза 5 — OCA | 1 седмица | PR submitted |
| **ОБЩО** | **11 седмици** | **~3 месеца** |

---

## Рискове

| Риск | Вероятност | Въздействие | Митигация |
|---|---|---|---|
| OCA review изисква съществени промени | Средна | Висок | Ранен precheck с OCA maintainer |
| GoRules не покрива всички T0 случаи | Ниска | Среден | cDMN като fallback за constraints |
| Properties engine се промени в Odoo 18.x | Ниска | Висок | Тестове на всяка minor версия |
| PTAV matching изисква точно съответствие на имена | Висока | Среден | Валидация при запис на `design_params` |
| Индустриалните шаблони са непълни | Средна | Нисък | Demo данни + документация за разширение |

---

## Зависимости

- `mrp_bom_line_formula_quantity` — вече в OCA, само версионна съвместимост
- `stock_move_forced_lot_multi` — трябва PR **преди Фаза 3**
- `zen-engine` — `pip install`, без допълнителни зависимости
- `product_electrical_properties` — само идеен модел, **не е runtime зависимост**

---

## Definition of Done (DoD)

- [ ] Всички тестове минават (pytest, без skipове)
- [ ] pre-commit: `ruff`, `black`, OCA checks — без грешки
- [ ] `README.rst` попълнен за всеки модул
- [ ] Changelog (towncrier) актуален
- [ ] Demo данни работят при fresh инсталация
- [ ] PR описанието съдържа контекст, screenshots и тест инструкции

---

## TODO (текущ статус)

- [ ] Фаза 0: PR `stock_move_forced_lot_multi`
- [ ] Фаза 0: PR `stock_move_forced_lot_multi_dim`
- [ ] Фаза 1: `mrp_bom_formula_lot_dimension` — мост
- [ ] Фаза 2: `mrp.design.param.definition` модел + XML парсер
- [ ] Фаза 2: `mrp.matrix.template` модел
- [ ] Фаза 2: `mrp.bom` разширение + `action_load_from_template()`
- [ ] Фаза 2: `mrp.bom.line` разширение (всички нови полета)
- [ ] Фаза 2: `stock.lot` разширение + Properties
- [ ] Фаза 2: `ace_editor` widget
- [ ] Фаза 3: GoRules wrapper клас
- [ ] Фаза 3: `_generate_design_matrix_moves()`
- [ ] Фаза 3: `_resolve_variant_by_ptav()`
- [ ] Фаза 3: `_create_child_lot()` + `_find_matching_lot()`
- [ ] Фаза 4: субмодули bags / corrugated / roller_door / security_door / interior_door
- [ ] Фаза 5: PR → OCA
