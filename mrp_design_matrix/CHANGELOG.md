# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.12.0] - 2026-05-25

### Added — TΦ derive_expression + lookup_tables (Phase B)

- **`mrp.matrix.template.lookup_tables`** (Json) + 7-ми notebook tab
  "Lookup Tables" с ace JSON widget. Named lookup таблици достъпни от
  TΦ `derive_expression` rules.
- **`mrp.bom.lookup_tables`** (Json) + fallback на template-а.
  `action_load_from_template` копира и него.
- **`_make_lookup(lookup_tables)`** staticmethod — builds a `lookup(name, *keys)`
  helper за safe_eval namespace. Semantics:
  - Navigate ``tables[name][str(key1)][str(key2)]...``
  - Last key + list-of-tuples value → ordered numeric threshold matching
    (first ``threshold >= float(last_key)`` → returns paired value). Полезно
    за height-based box selection и подобни ordered lookups.
  - Last key + dict value → direct ``str(last)`` lookup.
  - None при missing path.
- **`_evaluate_cascade` + `_configurator_evaluate_cascade`** разширени:
  след zen-engine eval, за всеки rule с `derive_expression`:
  - safe_eval с namespace = full context (current param values) + helpers
    (`lookup`, `min`, `max`, `abs`, `int`, `float`, `str`, `round`, `len`)
  - Result populates `derive_value` в response — клиентът получава
    already-resolved value, не raw expression.
  - Failed expressions log-ват warning и се skip-ват (не crash-ват).

### Output schema extension

- `derive_expression` (string) — нов output cell. safe_eval expression срещу
  current param context + helpers. Алтернатива на `copy_from` / `derive_value`.
  При successful eval → server set-ва `derive_value` в response (transparent
  за клиента).

### Use case (от teolino_shutters seed)

3 box-by-height rules: когато се промени `Height (mm)`, `slat_size` или
`shutter_model` → `box_size` се авто-избира чрез
`lookup("box_by_height", shutter_model, slat_size, height)`. `only_if_empty=false`
→ винаги override (box е strictly derived от H/slat/model). Заменя
`BOX_BY_HEIGHT_AND_SLAT` Python/JS dict от teolino_constraints.js
(marked @deprecated).

## [18.0.1.11.0] - 2026-05-25

### Added — TΦ Cascade Resolutions (Phase A от universal engine vision)

- **`mrp.matrix.template.cascade_table`** (Json) + 6-ти notebook tab
  "TΦ — Cascade" с `design_matrix` widget (`tphi` table_type).
- **`mrp.bom.cascade_table`** (Json) + tab във form-а; `action_load_from_template`
  копира и него.
- **`mrp.matrix.template._evaluate_cascade(changed_param, context)`** — eval
  на cascade_table през `ZenWrapper.evaluate`. Inject-ва `changed_param` в
  context-а като input.
- **`mrp.matrix.template._normalize_cascade(raw)`** — нормализира zen output
  до `{target_param: {copy_from?, derive_value?, only_if_empty?}}`. За
  multiple rules за един target: last write wins (rule order canonical).
- **`mrp.bom._configurator_evaluate_cascade(bom_id, changed_param, context)`**
  — `@api.model` RPC endpoint за OWL widget. BoM-копието има приоритет;
  fallback на template-а.

### Output schema

- `target_param` (string, required) — кой param да получи стойност
- `copy_from` (string) — име на param чиято current value да копираме
- `derive_value` (any) — explicit стойност (alternative)
- `only_if_empty` (bool, default true) — guard срещу overwriting на explicit
  user choice. Treats `""`, `null`, `false`, `"use_main"` като "empty".

### Use case (от teolino_shutters seed)

12 правила за color cascade: когато `main_color` се промени → всеки от 12-те
`color_*` sub-property params получава новата стойност (само ако още не е
explicit user choice). Заменя `_teolinoColorCascade` от
`teolino_sale_design_configurator_ui` (което остана като deprecated
no-op fallback за legacy BoM-ове без cascade_table).

### Roadmap

- Phase B: `derive_value` + `derive_expression` за box-by-height lookup
- Phase C: TΩ Multiplicity (per-shutter L/H expansion)
- Phase D: TΛ Layout (UX hints)
- Phase E: TΠ integration cleanup в VK module

Виж [[project_matrix_universal_engine_vision]] в memory за детайлен план.

## [18.0.1.10.0] - 2026-05-23

### Added

- **TΠ — Param Availability** (5-ти DMN слой). Reactive UI control table,
  консумирана от `sale_design_configurator` на всяка промяна на param.
  Изпреварваща disable/restrict логика — отрязва invalid комбинации в
  момента на избор, преди да станат T0 errors.
  - `mrp.matrix.template.availability_table` (Json) + 5-ти notebook tab
    (`design_matrix` widget с `options="{'table_type': 'tpi'}"`).
  - `mrp.bom.availability_table` (Json) + `action_load_from_template`
    копира и него; нов tab във form-а.
  - `mrp.matrix.template._evaluate_availability(context)` — eval през
    `ZenWrapper.evaluate`.
  - `mrp.matrix.template._normalize_availability(raw)` — превръща zen-output
    в `{param: {visible?, enabled?, allowed_values?, default_override?}}`.
    Merge logic: `visible`/`enabled` се AND-натрупват (false побеждава);
    `allowed_values` се intersect-ват (по-рестриктивно); `default_override`
    е last-write-wins.
  - `mrp.bom._configurator_evaluate_availability(bom_id, context)` —
    `@api.model` RPC endpoint за OWL widget-а; чете BoM-копието с
    fallback на template-а.
- `DesignMatrixField` OWL widget разпознава `table_type: 'tpi'` (за
  display name "TΠ Availability" в `_createEmptyJDM`).

### Known limitations

- TΠ eval-ът е server-side roundtrip per param change (debounced 150ms).
  За много fast slider-driving може да усетите latency; future optimisation:
  client-side JDM eval или зен-engine WASM bundle.

## [18.0.1.9.0] - 2026-05-23

### Changed

- `DesignMatrixField` OWL widget вече толерира двата JDM формата:
  - Legacy bare-table (`'type': 'decisionTable'` в `nodes[0]`) — както досега.
  - Modern wrapped graph (`inputNode → decisionTableNode → outputNode` + `edges`)
    от zen-engine ≥ 0.50 — `nodes[0]` става `inputNode`, затова `table` getter-ът
    и `_getContent()` сега филтрират първия node по type вместо да взимат `[0]`.
- `_createEmptyJDM()` emit-ва modern формат — нова таблица през "Create Table"
  бутона вече не изисква runtime патч от `ZenWrapper._migrate_node_types`.
- `confirmAddCol()` добавя `field: <colId>` на новите input/output колони.

### Added

- `mrp.matrix.template._extract_t2_coeff_keys(table_json)` — staticmethod,
  връща set от distinct `bom_line_coeff_key` стойности, които material_table
  emit-ва. Tolerира и двата decision-table node типа. Strip-ва JDM string-литерал
  кавичките.
- `mrp.matrix.template._get_t2_coeff_keys()` — convenience wrapper.
- `mrp.bom._check_t2_wiring()` — `@api.constrains` на `matrix_template_id`,
  `material_table` и `bom_line_ids.matrix_coeff_rule`. Сравнява T2 ключовете с
  тези, декларирани в `bom_line_ids.matrix_coeff_rule`. **Log warning, без raise**
  — T2 е optional layer и блокиран save би влошил UX. Цел: предупреждава за
  "висящ" T2 (виж audit от 2026-05-23 за BoM 580 на dev-teo-accounting — 5 ключа в
  T2, 0 декларации по 45 реда).

### Known limitations

- Записаните JDM payload-и (например в dev-teo-accounting templates 1 и 2)
  остават в legacy format — `_migrate_node_types` продължава да ги пач-ва на
  всеки evaluate. Auto write-back и BoM↔DPD auto-link migration са планирани,
  но изискват изрично разрешение защото пишат в потребителски данни на upgrade.

## [18.0.1.7.0] - 2026-04-29

### Fixed

- zen-engine >=0.50 compatibility: migrate legacy node types (`decisionTable` →
  `decisionTableNode`, `expression` → `expressionNode`, etc.) on every evaluate call.
- zen-engine >=0.50: inject missing `field` property on decision table
  inputs/outputs columns so the engine no longer rejects stored BoM tables.
- zen-engine >=0.50: wrap bare decision-table graphs (no `inputNode`/`outputNode`)
  with the required graph frame and edge stitching automatically.
- Normalize list output from `hitPolicy: collect` tables to the legacy
  `{"errors": [...], "warnings": [...]}` dict form expected by all callers.

## [18.0.1.6.0] - 2026-04-06

### Added

- T0 constraint table now passes non-reserved output keys (beyond
  `errors`/`warnings`) as context variables to T1/T2/T3 and BoM line
  formulas.  Enables condition-driven material injection.
- Formula `add_products` return: BoM line formulas can now inject
  extra raw material moves via `add_products = [{"ref": "...", "quantity": ...}]`.
  New helper `_create_formula_extra_move()` resolves product by recordset
  or XML ID and creates the stock move.

## [18.0.1.5.2] - 2026-04-05

### Reverted

- Post-migration script removed again — even with try/except guards,
  the upgrade still failed during its execution (probably the
  Properties-field search `('design_params', '=', False)` does not
  work the way we assumed in 18).  The script stays out until we
  can reproduce the exact error locally.

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
