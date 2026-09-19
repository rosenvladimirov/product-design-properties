# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.2.3.0] - 2026-09-19

### Added

- `add_products` is applied to the MO. Until now the formula result
  carried the list but only the design matrix consumed it; a plain MO
  ignored it. Each item (`product` or `ref`, `quantity`, optional `uom`)
  becomes an extra raw move of the same BoM line, a copy of the line's
  main move with its own product, quantity and UoM, flagged
  `formula_extra`. The same product twice is one move with the sum.
- Hook `mrp.production._formula_expand_add_products(bom_line)` — an
  extension that adds these moves itself returns False for its BoMs.

### Fixed

- Draft MOs with formula lines match their raw moves by
  (BoM line, product) instead of BoM line alone, so a change of the MO
  quantity no longer squashes the extra moves into the main one. A move
  whose line no longer yields values (`skip`, a product that left
  `add_products`) is now removed; the core compute kept it with its old
  quantity.

### Known limits

- Update BoM on a confirmed MO and backorders go through the core and do
  not re-run the formula; extra moves there keep their quantity.

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
