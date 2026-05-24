# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.1.1] - 2026-05-24

### Fixed

- `design.param.definition.full_design_params_definition` — добавен `search=`
  метод. Без него Odoo 18 хвърля
  `ValueError: Cannot convert design.param.definition.full_design_params_definition
  to SQL because it is not stored` при всеки domain filter върху полето
  (saved filters, search panels, или вътрешен Properties prefetch от
  records, чийто `design_params` field declarира
  `definition="design_param_definition_id.full_design_params_definition"` —
  напр. `stock.lot.design_params`, `product.product.design_params`,
  `product.template.design_params`).
  Симптом: RPC_ERROR на `design.param.definition` в `web_search_read`.
  Делегира search-а към `design_params_definition` (own definition); inherited
  стойности от parent chain не се match-ват, но common case `!= False` /
  `= False` (filter "non-empty") работи правилно.

## [18.0.1.0.3] - 2026-04-29

### Fixed

- Coerce `default` value from XML `<item name="default">` string to the
  declared `type` (integer/float/boolean) so Owl form widgets
  (`formatInteger`, `formatFloat`, Boolean checkbox) no longer crash
  when the stored default is a string.

## [18.0.1.0.2] - 2026-04-05

### Fixed

- Multi-company `ir.rule` for `design.param.definition`: explicit
  `company_ids = [(5, 0, 0)]` in `_process_properties` so definitions
  are always created as global (accessible by all companies).
