# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.4.0] - 2026-04-04

### Added

- **Matrix Preview** smart button on BoM form
  - Shows total rule count across all matrix tables
  - Opens `MatrixPreviewDialog` — simulation dialog with param controls (left) and real-time T0/T1/T2/T3 evaluation (right)
  - `RuleMatrixPreview` component moved here from sale_design_configurator (shared between BoM preview and SO configurator)
  - Loads param definition from BoM's linked `design_param_definition_id`
  - Loads BoM lines with `coeff_default` and `matrix_coeff_rule` for T2 Materials

*Assisted by Claude Code*

## [18.0.1.3.0] - 2026-04-04

### Added

- `DesignMatrixField` Phase 3 enhancements:
  - **JSON↔Table toggle** — switch between visual DMN table and raw JSON editor (dark theme textarea in edit, formatted pre in read mode)
  - **hitPolicy selector** — dropdown in edit mode to change between COLLECT / FIRST / PRIORITY, persists to JDM
  - **Drag-and-drop row reorder** — drag handle on rule rows in edit mode, HTML5 native DnD with visual drop indicators

*Assisted by Claude Code*

## [18.0.1.2.1] - 2026-04-02

### Fixed

- Smart cell encoding/decoding — user types `error` and widget auto-encodes to JDM `"error"` format
  - No manual quoting needed for string values
  - Booleans (`true`/`false`), numbers, operators (`> 3000`), JSON objects pass through unquoted
  - Existing JDM-quoted values decoded for display in edit mode

*Assisted by Claude Code*

## [18.0.1.2.0] - 2026-04-02

### Added

- `DesignMatrixField` edit mode (Phase 2)
  - Inline cell editing — all cells become `<input>` fields in edit mode
  - Add rule row (+ Rule button in toolbar)
  - Delete rule row (trash icon on hover)
  - Add input / output columns (+ Input, + Output buttons with inline name entry)
  - Remove columns (x button on column header hover)
  - Create empty table from blank field ("Create Table" button)
  - Auto-persist: every edit rebuilds JSON and updates the ORM record

*Assisted by Claude Code*

## [18.0.1.1.0] - 2026-04-02

### Added

- `DesignMatrixField` OWL widget — read-only DMN decision table renderer for GoRules JDM JSON fields
  - Replaces ACE JSON editor in BoM form for `constraint_table`, `geometry_table`, `material_table`, `operation_table`
  - Visual grid with input columns (blue) and output columns (green)
  - hitPolicy badge (COLLECT / FIRST / PRIORITY)
  - Collapsible sections with rule count
  - Error/warning level badges for T0 constraint tables
  - Smart cell formatting: wildcards (--), booleans, operators, JSON objects, quoted strings

*Assisted by Claude Code*
