# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## 19.0.1.49.5 — 2026-07-11

### Fixed
- A child-component parameter (e.g. a leaf/frame dimension like "Height (mm)")
  could appear twice in the left panel — once in the main parameter list and
  again in "Fine Tuning". `displayParams` excluded child params only by `name`
  (UUID), but the child definitions are merged into `full_design_params_definition`
  de-duplicated by `string` (label); when the two representations diverge the
  UUID guard misses. `displayParams` now also excludes by `string`, so a child
  param is shown only in its Fine Tuning section.

## 19.0.1.49.4 — 2026-07-11

### Fixed
- Accessory picture groups were duplicated when a component was emitted by both
  the texture channel (`get_template_variant_assets`) and `get_material_choices`.
  `accessoryVariants` is now de-duplicated by an exact signature (componentName +
  the sorted set of variant `ptav_name`s), so only byte-identical groups are
  dropped — a distinct selector is never removed. Conservative fix for the
  right-overlay double-accessory issue.

## [19.0.1.49.3] - 2026-07-09

### Fixed

- `design_configurator.js`: picking a colour recomputed the cost but did **not**
  repaint the 3D door. `_applyComponentColors()` was only called on model load;
  `onParamChange` ignored `cattr_*` (component colour/coating) keys. Now a
  `cattr_*` change calls `_applyComponentColors()` (reads only isColor attrs, has
  a mesh guard, continuous render loop shows it next frame).

## [19.0.1.49.2] - 2026-07-09

### Fixed

- `design_configurator.js`: added the missing `import { _t } from "@web/core/l10n/translation"`.
  `_t` was used in 10+ places (validation messages, `onConfirm` notifications) without being
  imported → `ReferenceError: _t is not defined` crashed the configurator on Confirm.

## [18.0.1.5.0] - 2026-04-04

### Added

- **Integration** (Phase 6) — auto-detect 3D/SVG/Matrix fallback
  - `showRulePreview` getter: shows `RuleMatrixPreview` when product has no GLB models, no SVG profiles, but has matrix tables
  - Conditional viewport: `RuleMatrixPreview` replaces Three.js canvas when applicable
  - BoM matrix tables (T0-T3) loaded via RPC in `DesignConfiguratorDialog`
  - BoM lines with `coeff_default` and `matrix_coeff_rule` loaded for T2 Materials
  - Props chain: Dialog → Widget → RuleMatrixPreview
  - Three.js init skipped when in rule preview mode (no wasted resources)

*Assisted by Claude Code*

## [18.0.1.4.0] - 2026-04-04

### Added

- `RuleMatrixPreview` T1/T2/T3 sections (Phase 5)
  - **T1 Geometry**: evaluate geometry_table rules, display computed key=value pairs, hitPolicy first/collect
  - **T2 Materials**: BoM composition with qty x coeff = final, matrix coefficient lookup, inactive O-variants greyed out, modified coefficients highlighted
  - **T3 Operations**: conditional workorder cards, active (green) / inactive (dashed grey), duration + workcenter metadata

*Assisted by Claude Code*

## [18.0.1.3.0] - 2026-04-04

### Added

- `RuleMatrixPreview` OWL component (Phase 4 — T0 Constraints)
  - Client-side GoRules JDM rule evaluation against current configurator params
  - Visual constraint rows: green (OK), red (error), yellow (warning)
  - Rule description builder from input conditions
  - Status summary badge (error count / warning count / All OK)

*Assisted by Claude Code*
