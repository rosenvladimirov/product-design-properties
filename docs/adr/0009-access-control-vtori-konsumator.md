# ADR-0009: `access_control` като втори консуматор на ZEN kernel (изоморфизъм A0–A3)

- **Статус:** приет (kernel извеждане ✅; access_control линия — частично/в развитие)
- **Дата на решението:** 2026-05-26
- **Дата на записа:** 2026-07-13 (консолидация)
- **Взето от:** Росен Владимиров
- **Източник на реконструкцията:** memory `products/design_matrix/project_base_zen_decision_2026_05_26` (изоморфизъм + Phase 2), `products/access_control/*` (2026-05)

## Контекст

При извеждането на `base_zen_decision` ([ADR-0002](0002-izvezhdane-base-zen-decision.md)) се идентифицира втори домейн със същата структура на решаване — контрол на достъп (карти/периметри/контролни точки). Въпросът: да се третира ли access_control като независим продукт, или като втори консуматор на същия ZEN kernel.

## Разгледани алтернативи

1. **Отделен собствен решаващ механизъм за access_control.** — Отхвърлено: дублира ZEN логиката.
2. **Втори консуматор на `base_zen_decision`, с изоморфен модел A0–A3.** — Прието.

## Решение

`access_control` ползва същия `base_zen_decision` kernel с изоморфен на T0–T3 модел:

| `mrp_design_matrix` (T0–T3) | `access_control` (A0–A3) | ZEN семантика |
|---|---|---|
| T0 constraints | A0 credential валиден? | guard rules |
| T1 context derive | A1 посока (физика) / прозорец (час) / parent-presence | context derive |
| T2 materials | A2 accept/deny | output rule |
| T3 operations | A3 ефекти (push/violation/occupancy) | output rule + side-effects |

Решения от спеката (2026-05-26): repo = `product-design-properties` (sibling); `access.credential` = MOVE с миграция; `hr_attendance_access_control` = bridge пласт завинаги (identity+UX), `access_control` = decision+spatial пласт (паралелни, не replace); direction derivation = HYBRID (Python helper произвежда `direction`+`anomaly_hint`, ZEN консумира — защото JDM е stateless и не може sequence/timing).

## Обосновка

Изоморфизмът доказва, че ZEN kernel-ът е наистина домейн-агностичен примитив, а не matrix-специфичен — което е самата обосновка за [ADR-0002](0002-izvezhdane-base-zen-decision.md). Един и същ JSON graph се изпълнява в Odoo и (по план) офлайн на Polimex контролер.

## Последици

- Затвърди kernel/glue pattern-а ([ADR-0008](0008-base-zen-decision-mrp-glue.md)).
- Наложи hybrid Python+ZEN за stateful преценки (ZEN сам не може timing/sequence).

## Произход на приноса (задължително, честно)

- Решението е взето от: **Росен** (спец + „ALL ANSWERED 2026-05-26 Rosen + agent").
- Имплементацията е: **с AI асистенция под надзор**; access_control линията е **частично реализирана / в развитие** към датата на записа (не завършен продукт).
- ⚠️ **Празнота (честно отбелязана):** котвата споменава „**N+M доктрина** (hardware/access control)" като кандидат-решение. В прегледаните memory източници **НЕ намерих документирана обосновка под точно това име**. Ако „N+M" е отделно хардуерно архитектурно решение, обосновката му не е документирана — не я измислям. Тук се документира само изоморфизмът A0–A3, който е реално засвидетелстван.
