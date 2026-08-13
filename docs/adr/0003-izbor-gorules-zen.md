# ADR-0003: Избор на GoRules ZEN Engine (MIT) като решаващ двигател

- **Статус:** приет
- **Дата на решението:** ок. 2026-05 (в сила при извеждането на `base_zen_decision`)
- **Дата на записа:** 2026-07-13 (консолидация)
- **Взето от:** Росен Владимиров
- **Източник на реконструкцията:** memory `products/design_matrix/project_base_zen_decision_2026_05_26` (#8), `anchor_design_matrix_engine_digest_2026_07_05`, `topics/licensing/licensing_master_reference` §6.3; `THIRD-PARTY-LICENSES.md` (ZEN MIT)

## Контекст

Матрицата се нуждае от decision-таблици (DMN-подобни), които се редактират като данни и се оценяват детерминирано — за геометрия, материали, операции. Нужен беше решаващ двигател с преносим JSON-graph формат, който да може да се изпълнява и вътре в Odoo, и офлайн на хардуерен контролер (за `access_control`).

## Разгледани алтернативи

1. **Собствен rule-евалуатор** (Python if/else или собствен DSL). — Отхвърлено: поддръжка, липса на стандартен формат, невъзможност за офлайн изпълнение на контролер.
2. **Тежък BRMS (напр. Drools/JVM).** — Отхвърлено: несъвместимо с Odoo/Python стека и с embedded контролер.
3. **GoRules ZEN Engine** (JDM/DMN формат, Rust core с Python binding, pip `zen-engine`). — Прието.

## Решение

`base_zen_decision` ползва **GoRules ZEN** през `zen-engine` (Python binding към Rust core). Таблиците се съхраняват като JSON graph (`inputNode → decisionTableNode → outputNode`), оценяват се stateless чрез `ZenEngine().create_decision(json).evaluate(ctx)`. Същият JSON graph се изпълнява и в Odoo, и (по план) в proxy/контролер чрез директен `pip install zen-engine`.

## Обосновка

- **Преносимост:** идентичен JSON-graph eval в Odoo и офлайн на контролер — байт-идентична семантика (memory #8).
- **Данни, не код:** правилата са JSON записи, редактируеми без промяна на програмата — стъпва пряко върху границата код/данни ([ADR-0005](0005-klientska-specifika-kato-danni.md)).
- **Лицензно чисто:** ZEN е **MIT** — не заразява AGPL/OPL веригата (licensing_master_reference §6.3; точният MIT текст е в `THIRD-PARTY-LICENSES.md`).

## Последици

- ZEN стана външна зависимост на kernel-а (`external_dependencies`: `zen`/`zen-engine`).
- Появиха се практически JDM-формат уроци (пълен граф + 2 edges; output id=name=field; иначе тих `result=[]`) — документирани в engine дайджеста.
- Отвори се път за офлайн изпълнение на контролер (Phase 3 от `base_zen_decision` спеката — все още план).

## Произход на приноса (задължително, честно)

- Решението е взето от: **Росен** (изборът на ZEN е част от спецификацията от 2026-05-26, #8).
- Имплементацията е: **с AI асистенция под надзор**.
- Забележки: `access_control`/контролер офлайн изпълнението (Phase 3) е **план, не имплементирано** към датата на записа — тук се документира изборът на двигател, не завършена офлайн интеграция.
