# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.1.0] - 2026-04-06

### Added

- Formula evaluation now detects `add_products` variable — a list of
  dicts with `product`/`ref`, `quantity`, and optional `uom` — and
  includes it in the result dict for the matrix engine to create
  additional raw material moves.

## [18.0.1.2.0] - 2026-04-05

### Security

- **BREAKING**: tightened access on `mrp.bom.line.formula.template`
  - Read: `mrp.group_mrp_user` (was: all logged-in users)
  - Write / create / delete: `mrp.group_mrp_manager` only
  - Reason: formulas are evaluated with full `env` in `safe_eval`
    globals and can call `.sudo()` / raw SQL via `env.cr`. Template
    authors therefore need admin-level trust.
- Added multi-company `ir.rule` on the template model.
- Added `CONTEXT.md` documenting the trust boundary explicitly.

### Fixed

- Moved `safe_eval` import in `stock_lot._create_child_lot` from inside
  a method to module level (companion fix in `mrp_design_matrix`).

## [18.0.1.1.0] - 2026-04-04

### Added

- Extended formula evaluation with three output variables:
  - `result` (or `quantity`) — computed quantity (float)
  - `product` — optional product override (recordset via `env.ref()`)
  - `uom` — optional UoM override (recordset via `env.ref()`)
- `env` available in formula context for `env.ref()`, model searches, etc.
- `design_context` injection support — when called from design matrix, formula has access to width, height, T1 geometry outputs, and all design params as flat variables
- Override `_get_move_raw_values()` to unpack product/uom overrides from formula result into stock.move values

*Assisted by Claude Code*
