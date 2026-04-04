# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
