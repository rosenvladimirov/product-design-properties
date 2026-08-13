# ADR-0008: Разделяне `base_zen_decision` → base-only + glue `base_zen_decision_mrp`

- **Статус:** приет
- **Дата на решението:** 2026-07-04
- **Дата на записа:** 2026-07-13 (консолидация)
- **Взето от:** Росен Владимиров
- **Източник на реконструкцията:** memory `anchor_design_matrix_engine_digest_2026_07_05` (двата engine фикса); git `product-design-properties` `2c5df0e` (2026-07-04, 18.0), `2f989c2` (19.0), `d365156` (20.0)

## Контекст

`base_zen_decision` (kernel, [ADR-0002](0002-izvezhdane-base-zen-decision.md)) съдържаше менюта (`menu_zen_root/table/log`) с `parent="mrp.menu_mrp_configuration"`, но `depends` само на `base`. При fresh install това чупеше (менюто сочи родител от `mrp`, който може да не е зареден) — нарушение на инвариант „kernel-ът не знае за mrp".

## Разгледани алтернативи

1. **Добавяне на `mrp` към depends на `base_zen_decision`.** — Отхвърлено: замърсява kernel-а с домейн зависимост (обратно на [ADR-0002](0002-izvezhdane-base-zen-decision.md)).
2. **Извеждане на mrp-специфичните менюта в отделен auto-install glue модул.** — Прието.

## Решение

Менютата са изнесени в **нов auto-install модул `base_zen_decision_mrp`** (`depends`: `base_zen_decision` + `mrp`). `base_zen_decision` вече инсталира чисто само с `base`. Референциите се сменят: `base_zen_decision.menu_zen_root` → `base_zen_decision_mrp.menu_zen_root`.

## Обосновка

Пази инварианта „kernel без домейн знание" ([ADR-0002](0002-izvezhdane-base-zen-decision.md)) чист, като изтегля mrp-връзката в тънък glue пласт — вместо да замърси kernel-а. Структурно решение, не просто bugfix: създава ясен glue пласт между kernel и домейн.

## Последици

- `base_zen_decision` инсталира без `mrp` (поправен fresh-install срив).
- Който реферира `base_zen_decision.menu_zen_root` трябва да мигрира към `base_zen_decision_mrp`.
- Затвърждава pattern-а „kernel + auto-install glue per домейн" (виж и [ADR-0009](0009-access-control-izomorfizam.md)).

## Произход на приноса (задължително, честно)

- Решението е взето от: **Росен** (одобри двата engine фикса 2026-07-05; pushed).
- Имплементацията е: **с AI асистенция под надзор**.
- Забележки: този ADR е граничен между „bugfix" и „архитектурно решение" — включен е, защото създава нов пласт (glue) и променя референтната повърхност. Свързаният double-move фикс (`676095c`) е чист bugfix и НЕ получава ADR.
