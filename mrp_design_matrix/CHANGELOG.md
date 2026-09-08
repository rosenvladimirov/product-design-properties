# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.3.12.0] - 2026-09-08

### Added

- Shop floor context on `mrp.routing.workcenter`. One shop measurement
  carries five things about an operation and Odoo had room only for the
  duration, so the barcode lived inside the operation NAME (15 operations
  carry it in brackets, one carries two at once) and the frequency, the
  source and the calendar time had nowhere to go at all:
  - `shop_barcode` — the barcode(s) as scanned, comma separated when one
    operation covers several. 🔑 The name is a translatable field, so a
    barcode written there cannot be matched against scan data; this one can.
  - `semi_finished` — which part the operation works on (metal/wood frame,
    metal/wood leaf, profiles, aluminium frame, edging, painted parts, final
    assembly, quality), so operations follow the parts instead of one row
    per work center.
  - `time_calendar` — the calendar time (a full operator day divided by the
    median doors), for capacity; the clean time in `time_cycle_manual` stays
    the basis for labour cost. Both are needed, they differ by 1-2x.
  - `time_source` — measured / shop log / norm 2011 / norm 2016 / estimate.
    A measured time and an estimate are not equally trustworthy, and that
    has to survive in the data.
  - `shop_frequency` — the measured share of doors passing the operation.
    Below 1.0 means conditional in practice, even when nothing marks it so.
- `action_fill_shop_barcode_from_name()` reads the barcodes out of existing
  operation names into the new field. Deliberately a manual action and not
  an upgrade hook — it writes on live operations, and it never overwrites a
  barcode that is already set.

*Assisted by Claude Code*

## [19.0.3.11.0] - 2026-09-08

### Added

- Lot names resolved from the COMBINATION. When the product carries a lot
  prefix template in its design properties (`{series}{lock_points}`), the
  prefix is resolved against the design context and **every new combination
  gets its own sequence** — found by prefix, or created on first use.
- The sequence lookup follows the same contract as the core inverse of
  `product.template.serial_prefix_format` (lookup by prefix alone, new
  records with code `stock.lot.serial`, padding 7, no company), so both
  sides serve one sequence per prefix instead of handing out the same
  numbers from two.
- An unresolvable template, or one producing a `%` (which `ir.sequence`
  interpolates), is reported and the lot falls back to the product
  sequence — the number is never silently wrong.

### Changed

- Child lots no longer pass an explicit name, so Odoo's own
  `stock.lot._compute_name` (or the combination) decides it. An explicit
  name bypassed both.
- `_generate_child_lot_name` is now only the last resort for a product with
  no sequence at all. 🚨 Its `next_by_code("stock.lot.serial")` is gone: the
  core creates one record with that code per prefix, so a lookup by code
  alone got less predictable with every prefix added.

*Assisted by Claude Code*

## [19.0.1.6.0] - 2026-04-06

### Added

- T0 constraint table now passes non-reserved output keys (beyond
  `errors`/`warnings`) as context variables to T1/T2/T3 and BoM line
  formulas.  Enables condition-driven material injection.
- Formula `add_products` return: BoM line formulas can now inject
  extra raw material moves via `add_products = [{"ref": "...", "quantity": ...}]`.
  New helper `_create_formula_extra_move()` resolves product by recordset
  or XML ID and creates the stock move.

### Fixed

- `__manifest__.py` version prefix changed from `18.0` to `19.0` — Odoo 19
  rejected the module as incompatible and refused to load it.

## [18.0.1.5.0] - 2026-04-05

### Performance

- `_generate_design_matrix_moves` refactored into step helpers
  (`_eval_t0_constraints`, `_eval_t1_geometry`, `_eval_t2_materials`,
  `_generate_bom_line_moves`, `_generate_t2_adhoc_moves`).
- **T2 `material_table` now evaluated once per MO** instead of once
  per BoM line.  A 50-line BoM with O-variants used to call
  `ZenWrapper.evaluate` 51× with the same arguments; it now calls it
  once.  New helper `_eval_matrix_coeff_cached(line, coeff_by_key)`
  performs dict lookup instead of re-evaluation.
- `bom_line_ids.fetch([...])` batch prefetch before the move-generation
  loop turns N+1 SELECTs into a single query for large BoMs.
- Old `_eval_matrix_coeff(line, ctx)` kept for backward compatibility
  with external callers but marked deprecated in the docstring.

### Added

- Soft fallback when `zen-engine` is not installed.  Set the system
  parameter `mrp_design_matrix.allow_missing_zen_engine` to `1` and
  the matrix engine becomes a no-op — MO creation continues with the
  standard OCA behaviour for BoMs without matrix tables.  T0
  constraints are NOT enforced in this mode; use only for staged
  rollouts.
- Post-migration script (`migrations/18.0.1.5.0/post-migration.py`):
  - warns about BoMs that have matrix tables but no
    `design_param_definition_id`
  - back-fills empty `design_params` on lots that already link a
    definition
  - emits a loud log line if `zen-engine` is missing at upgrade time

## [18.0.1.4.1] - 2026-04-05

### Fixed

- `stock_lot._create_child_lot`: moved `safe_eval` import to module
  level and added explicit warning log on extraction failures.

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
