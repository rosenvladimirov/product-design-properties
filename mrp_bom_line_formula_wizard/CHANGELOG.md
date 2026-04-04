# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.1.0] - 2026-04-04

### Added

- **Load from Template** — dropdown to pick a formula template and populate the editor
- Updated help text with new output variables: `result`, `product`, `uom`
- Documented `env` access and design context variables (width, height, etc.)
- Examples: area-based formula, product override with condition

### Changed

- Depends on `mrp_bom_line_formula_template` (required for template picker)
- Placeholder updated to use `result =` syntax

*Assisted by Claude Code*
