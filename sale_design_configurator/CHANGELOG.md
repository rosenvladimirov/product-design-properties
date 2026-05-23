# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.8.0] - 2026-05-23

### Added

- TΠ availability — reactive UI control в `DesignConfiguratorWidget`:
  - Нови props: `availabilityTable` (Json) + `bomId` (Number).
  - `this.ui.availability` state — populated на всеки `onParamChange` чрез
    `mrp.bom._configurator_evaluate_availability(bom_id, context)` (debounced
    150ms, clearTimeout на unmount).
  - `_buildAvailabilityContext()` подава както hash имена (`f7692…`), така
    и string ключове (`shutter_model`) — TΠ rules могат да match-нат и по
    двата.
  - `_enforceAvailability()` — auto-apply на `default_override` ако текущата
    стойност излиза от `allowed_values` (напр. switching на `shutter_model`
    отрязва невалиден `shutter_count` → auto-set на `"1"`).
  - `displayParams` + `childDisplayParams` getter-и са декорирани с
    `_decorateParam()` — filter-ват `selection` опции до `allowed_values`
    и излагат `tpiVisible` / `tpiEnabled` за template-а.
  - XML template-а уважава `param.tpiEnabled === false` — добавя CSS клас
    `o_cfg_disabled` (opacity 0.45, pointer-events:none) + HTML `disabled`
    атрибут на input/button.
- `DesignConfiguratorDialog` чете `availability_table` от BoM-а и подава
  `bomId` + `availabilityTable` на widget-а. Defaults на false → когато
  BoM-ът няма TΠ, widget-ът се държи както досега.

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
