# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
