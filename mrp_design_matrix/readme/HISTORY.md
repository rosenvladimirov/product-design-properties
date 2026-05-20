# Changelog

## 19.0.1.9.0 — 2026-05-20

### Подобрения

- `industry` свободен Char на `mrp.matrix.template` преминава в
  `industry_id` Many2one към новия модел `design.industry` (canonical
  таксономия + INDUSTRY_ALIASES full-normalization map). Zero-churn за
  съществуващите индустриални под-модули — `create`/`write` override
  резолва легитимните `industry="…"` стойности преди ORM.
- Документацията (README + `readme/*.md`) е преведена на български.

## 19.0.1.8.0 — 2026-04-16

### Корекции

- Миграция към Odoo 19 `mrp.production.lot_producing_ids` (преди беше
  `lot_producing_id` Many2one; сега One2many). Ползва
  `lot_producing_ids[:1]` като design lot.
- `stock.lot._get_design_context()` сега превежда UUID ключовете към
  schema `string` имена и display label-ите към raw selection
  стойностите, така че T1/T2/T3 правилата мачват записаните на lot-а
  стойности.
- `_eval_t0_constraints` приема и list (zen-engine 0.53+ `collect`
  hit policy), и dict (legacy) shape на връщане.
- `_create_or_update_matrix_move` пише в `stock.move.reference` вместо
  в премахнатото `stock.move.name`.
- `_unpack_formula_result` извиква `_resolve_variant_by_ptav` за
  O-вариантни BoM линии с дефиниран `param_attribute_map`, така че
  избраното от матрицата move ползва правилния вариант от design
  контекста — не статичния placeholder, записан върху BoM линията.

### Известни проблеми

- Дублирани move_raw линии: стандартният MRP и matrix engine-ът
  генерират move-ове за една и съща BoM линия. Планирана корекция в
  19.0.1.9.0.
- XML `eval=""` matrix templates все още ползват Python dict литерали,
  които fresh install връща към старата zen schema. Миграцията на XML
  файловете се води като отделен commit в repo-то.

## 19.0.1.7.0 — 2026-04-16

### Корекции

- Helper за миграция на matrix template JDM-а (string → node schema,
  edges, `field` на I/O, wildcard `""` за липсващи input id-та в
  правилата).

## 19.0.1.6.0 — 2026-04-12

### Корекции

- Начална работа по съвместимост с Odoo 19 + zen-engine 0.53 (върната
  и преправена в 19.0.1.7/8.0).

## 19.0.1.0.0 — 2026-03 (първа версия)

- Параметричен BoM, задвижван от lot-level design параметри и DMN
  правилна матрица. T0/T1/T2/T3 таблици през GoRules zen-engine.
