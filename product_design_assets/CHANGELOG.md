# Changelog — product_design_assets

All notable changes to this module are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [19.0.1.1.0] - 2026-09-08

### Added
- Lot prefix carried by the product design properties. A design parameter
  whose canonical name (`formula_name`) is `lot_prefix` is pushed onto the
  standard `product.template.serial_prefix_format` on create and on every
  write that touches `design_properties` or `design_param_definition_id`.
- Odoo's own lot machinery is left untouched: naming stays in
  `stock.lot._compute_name` (from `product_id.lot_sequence_id`) and the
  sequence is still found or created by the core inverse of
  `serial_prefix_format`. This module only decides *which* prefix applies,
  so a range no longer has to be numbered by hand template by template.
- Variants of one template asking for different prefixes are left unchanged
  and logged as a warning — a template carries a single sequence, and
  guessing a winner would silently renumber a range.

### Changed
- `depends` now lists `stock` explicitly (it was only reachable through
  `mrp`), because the module writes a `stock` field.

*Assisted by Claude Code*
