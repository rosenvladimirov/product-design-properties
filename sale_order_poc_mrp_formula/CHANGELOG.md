# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] - 2026-09-20

### Added

- Initial release: Stage 2 of the production configuration (ADR
  sale-order-poc/0005). The configuration feeds the BoM line quantity
  formulas of `mrp_bom_line_formula_template`: its parameters by their
  codes, plus the production context (`poc`, `lot`, `mo_qty`, `ceil`…).
  The contract is explicit and never shadows a base key of the engine.
- A table parameter reaches the manufacturing order: a formula returns
  `add_products` built from the table rows, and the bridge keeps those
  extra components when it recomputes.
- Button "Check Configuration Formulas" on the Bill of Material: the only
  guard against a mistyped name, because a formula error does not stop
  production — it silently gives the standard quantity (ADR
  sale-order-poc/0006).
- `pre_init_hook`: refuses `mrp_bom_line_formula_template` older than
  19.0.2.3.0 and the abandoned fork `mrp_bom_line_formula_quantity`.
- AGPL-3, auto installed when both sides are there; no LGPL or OPL module
  depends on it (ADR sale-order-poc/0005).
- Bulgarian translation. Tests with the real engine and mutations.

*Assisted by Claude Code*
