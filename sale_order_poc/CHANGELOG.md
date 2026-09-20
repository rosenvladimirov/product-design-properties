# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.2.0] - 2026-09-20

### Added

- `_poc_render(text, fmt, extra)` — `{{ code }}` becomes the value, without
  eval. A line whose value is empty falls out entirely, a selection shows
  its label, a number its digits and suffix, and `fmt="html"` escapes.
  The work order layer builds the Shop Floor note and the quality
  instructions with it (ADR sale-order-poc/0010).

*Assisted by Claude Code*

## [19.0.1.1.0] - 2026-09-20

### Added

- Aspects: a template with usage "aspect" is added to one configuration
  (printing, label, packing scheme) and brings its own parameters. The
  codes of the main template and of the allowed aspects may not overlap,
  so the formulas see one flat space. A template may give default
  aspects (ADR sale-order-poc/0004).
- Table parameters: a parameter of type "table" is not a property; it
  declares child rows (key, product, value, unit). In a formula the table
  is a list of rows ordered by sequence; an empty cell is a missing row,
  not a zero. Tables reach the manufacturing order through the
  `add_products` output of the formula (ADR sale-order-poc/0012).
- After confirmation the aspects and the table rows are user data: only a
  configuration manager changes them.

### Known limits

- The related `poc_params` on the lot, the manufacturing order and the
  work order show only the MAIN container: Properties has exactly one
  definition record per field. The aspects are read through the
  configuration.

*Assisted by Claude Code*

## [19.0.1.0.1] - 2026-09-19

### Added

- Bulgarian translation (`i18n/bg.po`, 202 terms). Lot and batch are two
  terms: "Лот" and "Партида".
- License graph test: the module is LGPL-3, depends on no AGPL or
  proprietary module (transitively), and every file carries the LGPL
  header (ADR sale-order-poc/0005).
- A salesman with sales rights only (no inventory rights) configures and
  confirms an order.
- Browser tours: a sales-only user fills and saves the parameters (the
  computed ones are written on save, not live); a manager reaches the
  properties definition editor, whose save the template guard refuses.

### Fixed

- A sales-only user could not open a configuration at all: the form read
  its lots, and only inventory users may read `stock.lot`. The lot fields
  and the Lots button are now shown to inventory users only.

*Assisted by Claude Code*

## [19.0.1.0.0] - 2026-09-19

### Added

- Initial release: Production Configuration (POC) of a sale order line —
  the generic carrier of production parameters, independent of any
  company (ADR sale-order-poc/0001–0011).
- `sale.order.poc.param` — dictionary of parameters: one code is one
  type in the whole database; the code is both the property name and the
  formula variable. Reserved names of the formula contracts are refused.
- `sale.order.poc.template` / `.line` — which parameters a kind of
  product has, sections, required flag, formula. The properties
  definition is COMPUTED from the lines and cannot be written, so the
  properties widget cannot create a parameter with a random name.
  Formula cycles are refused on save; formulas run once, in dependency
  order.
- `sale.order.poc` — deal in columns, specification in `params`
  (Properties by template). One reader `_poc_values()` (selection key,
  0 stays 0) and one writer `_poc_set_params()`. Computed parameters
  keep their origin (`param_origins`: formula / manual) with
  `allow_manual` and `allow_fallback` per template line.
- Sale flow: configuration button on the order line; confirmation needs
  a configuration with all required values; a line added to a confirmed
  order waits for "Release to Production"; copy and cancel follow the
  order. After confirmation only a configuration manager changes the
  parameters, and every change is posted as "code: old → new".
- Lot of the configuration: `stock.lot.poc_id` / `poc_batch`, the lot is
  created right before procurement; `poc_id` travels on the moves and a
  restricted move reserves only from its own lot family, without
  OCA `stock_restrict_lot`.
  The lot name comes from the product's lot prefix; a product without a
  lot sequence takes Odoo's standard "Serial Numbers" sequence
  (ADR sale-order-poc/0013).
- `product.template.poc_template_id` and `poc_default_params`.
- Demo template, 37 tests.

*Assisted by Claude Code*
