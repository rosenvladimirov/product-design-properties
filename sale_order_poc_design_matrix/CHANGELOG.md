# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] - 2026-09-22

### Added

- Initial release (ADR sale-order-poc/0019): the production configuration of
  the sale order line feeds the design matrix by name, one to one. A
  configuration code equal to the name (`string`) of a matrix parameter feeds
  it; nothing else is touched. A record (a product variant, for example)
  becomes the raw key of the matrix selection; an empty record is no value.
- `_poc_matrix_context()`: the defaults of the design definition plus the
  values of the configuration, in the shape the configurator uses. The
  definition is the one of the sale configurator when it is installed, else
  the one of the product, else the one of the bill of materials.
- At confirmation the lot of the configuration carries the matrix
  parameters: the defaults of the definition plus the configuration values.
  A lot of the same definition keeps its own values; the configuration
  writes only its codes.
- Does not depend on `sale_design_configurator`: works in a plant that opens
  the matrix only in manufacturing. The configurator part is
  `sale_order_poc_design_configurator`.
- AGPL-3, auto installed when both sides are there; no LGPL or OPL module
  depends on it (ADR sale-order-poc/0005).
- Tests, including one that fails if the configurator enters the dependency
  closure, and mutations.

*Assisted by Claude Code*
