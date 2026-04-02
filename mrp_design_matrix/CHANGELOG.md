# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
