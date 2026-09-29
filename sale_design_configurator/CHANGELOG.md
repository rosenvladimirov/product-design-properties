# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.2.2.1] - 2026-09-22

### Fixed

- The cube on the sales order line opens the dialog directly, not
  through `action_open_design_configurator`, so the line never reached
  the vertical hook and the configurator opened on the defaults. The
  cube now passes the line too.
- `get_design_definition_for_product` may answer `autoOpen: false`: a
  vertical that leads the line another way stops the configurator from
  opening by itself on product change.
- The cube honours its `invisible` on the sales order line. Odoo 19 lists
  render a `<widget>` cell regardless of `invisible`, so
  `not has_design_definition` never hid it; the widget now evaluates
  the expression itself.

## [19.0.2.2.0] - 2026-09-21

### Added

- The configurator opened from a sales order line passes the line to
  the vertical hook (`get_param_patch`, context `design_sale_line_id`).
  A vertical that knows the line — the production configuration of the
  sale — imposes its values and locks them, instead of the configurator
  opening on the definition defaults.

## [19.0.2.1.2] - 2026-09-21

### Fixed

- Carried over from the Solid tree: the design context handed to the
  configurator read `product_template_variant_value_ids`, which the core
  narrows to attribute lines with more than one value. A single-value line
  was therefore missing from the configurator's context while production
  read it — the same product, two different contexts.
- Restored after the merge with the Packit tree, whose 2.x copy had split
  off before them: the lot name follows the combination again
  (19.0.1.50.0), picking a colour repaints the 3D model (19.0.1.49.3), an
  accessory reached from two channels is shown once (19.0.1.49.4), and a
  child-component parameter is no longer repeated in the main panel
  (19.0.1.49.5).

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

## [19.0.1.50.0] - 2026-09-08

### Changed

- `generate_design_lot_name` now takes the combination (`design_params`,
  `definition_id`) and answers from the first source available: the
  sequence of that combination (prefix template), then the product category
  sequence, then the product's own `lot_sequence_id`, then the
  product-based fallback.
- 🚨 The old `next_by_code("stock.lot.serial")` step is replaced by the
  product's `lot_sequence_id`. The core creates one sequence with that very
  code per prefix, so the lookup by code alone returned an arbitrary one of
  them — and got worse with every prefix anyone added.
- The configurator (JS) passes the collected design parameters along with
  the product, so a combination can decide its own series.

*Assisted by Claude Code*

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
