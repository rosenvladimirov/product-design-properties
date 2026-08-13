# ADR-0002: Извеждане на `base_zen_decision` kernel от `mrp_design_matrix`

- **Статус:** приет
- **Дата на решението:** 2026-05-26 (спецификация); изпълнено 2026-05-30
- **Дата на записа:** 2026-07-13 (консолидация)
- **Взето от:** Росен Владимиров
- **Източник на реконструкцията:** memory `products/design_matrix/project_base_zen_decision_2026_05_26`; git комити `1097459`/`1ab9e33` (2026-05-30, „[REF] Extract base_zen_decision kernel from mrp_design_matrix (Decision #4 Step 2)")

## Контекст

ZEN-решаващата логика (`ZenWrapper`/`zen_engine.py`, ~139 реда) живееше вътре в `mrp_design_matrix`. Появи се втори потенциален консуматор със същия подход — `access_control` (контрол на достъп, A0–A3), който също се нуждае от ZEN evaluate/trace/version, без да е свързан с производство. Решаващият примитив трябваше да е независим от домейна.

## Разгледани алтернативи

Спецификацията на Росен (2026-05-26) постави изричен избор (Decision #4):
1. **Оставяне на kernel-а вътре в `mrp_design_matrix`** засега, split по-късно. — Първоначално записано като възможен път.
2. **Извеждане в отделен модул в същото репо (sibling), без нов repo/addons-path.** — Избрано (Росен избра „вариант 2"/Option 1: same repo sibling) и изпълнено на 2026-05-30.
3. Нов отделен repo. — Отхвърлено (излишна addons-path сложност).

## Решение

Създаден нов модул **`base_zen_decision`** в `product-design-properties` — ZEN evaluator kernel БЕЗ домейн знание (само: load graph + evaluate + trace + version + sync). ZEN файловете (`zen_engine.py`, `zen_decision_table.py`, `zen_decision_log.py`, тестове, views, ACL) са преместени с `git mv` (историята запазена). `pre_init_hook` reassign-ва `ir_model_data` ownership на `zen.*` от `mrp_design_matrix` към `base_zen_decision` — adopt-ва живите таблици без да ги дропва. `mrp_design_matrix` 2.0.0→2.1.0: `depends += base_zen_decision`.

## Обосновка

Изомо鰭фни домейни (производствена матрица T0–T3 и контрол на достъп A0–A3) споделят един и същ ZEN примитив. Изнасянето му като самостоятелно ядро прави примитива преизползваем, тестируем и версионируем независимо, и позволява същата JSON-graph семантика да се изпълнява и в Odoo, и офлайн на контролер (виж [ADR-0003](0003-izbor-gorules-zen.md)).

## Последици

- `base_zen_decision` стана самостоятелен базов примитив (по-късно допълнително разделен — виж [ADR-0008](0008-base-zen-decision-mrp-glue.md)).
- Live-verified при извеждането: `pre_init_hook` adopt-на 48 реда; трите модула инсталирани чисто.
- Създаде основа за `access_control` линията ([ADR-0009](0009-access-control-izomorfizam.md)).

## Произход на приноса (задължително, честно)

- Решението е взето от: **Росен** — спецификация `~/Свалени/CLAUDE_base_zen_decision.md`, изборите „ALL ANSWERED 2026-05-26 (Rosen + agent)".
- Имплементацията е: **с AI асистенция под надзор** (Decision #4, стъпка 2 — Росен избра варианта; агентът изпълни git mv + hook).
- Забележки: част от решенията в спецификацията са формулирани съвместно (Rosen + agent) — Росен е избиращата страна по всяка точка.
