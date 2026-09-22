# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] - 2026-09-22

### Added

- Initial release (ADR sale-order-poc/0019), generalised from the Packit
  bridge `packit_poc_design` 19.0.1.8.0 so that every plant with the sale
  configurator gets it.
- One order, one lot: the configuration adopts the design lot of the sale
  order line instead of opening a second one; a lot of another configuration
  is refused, a lot of another product is left alone. At confirmation the lot
  of the configuration becomes the design lot of the line and moves to
  "Sales Confirmed" as a system step, so a salesman without inventory rights
  confirms.
- The design configurator of the line opens with the values of the
  configuration, locked, until the design lot is fixed; afterwards the matrix
  reads the lot. Every selection managed by the configuration that differs
  from the screen loads its dependent parameters through the vertical hook
  (`get_param_patch`), as a choice on the screen does; before, only the board
  material of the corrugated vertical did.
- The configurator no longer opens by itself for a product with a
  configuration template: the quotation goes through the configuration.
- Line icons: the configuration icon on the quotation, the design cube on the
  confirmed order.
- Price of the quotation from the matrix: a dry run of the matrix, the
  standard bill of materials costing and the reference price engine (soft
  dependency, OPL-1). Fields `Matrix Unit Cost` (design managers only),
  `Matrix Unit Price`, `Matrix Price Note`; a price changed by hand is kept.
- Requires the sale configurator that passes the sale order line to the hook
  (`design_sale_line_id`) and returns `autoOpen`, and `mrp_design_matrix_cost`
  with the work centre and unit of measure in the dry run (19.0.1.8.1).
- Bulgarian translation. Tests with a browser tour and mutations.

*Assisted by Claude Code*
