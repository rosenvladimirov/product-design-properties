# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.11.0] - 2026-05-25

### Added — TΩ + TΛ widget consumption (Phase E)

- `DesignConfiguratorWidget`:
  - Нови props: `multiplicityTable`, `layoutTable` (Json, optional).
  - Getter `multiplicityMetadata` — extract {count_param, per_instance_params,
    aggregator} от TΩ rule (strips JDM quoting + parses list literals).
  - Getter `multiplicityCount` — current count value за UI iteration.
  - Method `getLayoutForParam(paramKey)` — TΛ layout state {section?,
    widget_hint?, customer_visible?, submodal?} per DPD string ключ.
  - Convenience `isCustomerVisibleParam(paramKey)` — default true backward
    compat (когато TΛ не казва нищо).
- `DesignConfiguratorDialog` чете `multiplicity_table` + `layout_table` от
  BoM и passes-ва ги. Defaults на false → widget работи както досега за
  BoM-ове без новите слоеве.

### Use case

VK template (teolino_dialog.xml) ИЛИ бъдещи customer UI templates вече могат
да викат `this.multiplicityCount` вместо hardcoded `teolinoShutterCount()`,
`getLayoutForParam(...).customer_visible` вместо `CUSTOMER_PICKABLE_COLOR_KEYS`,
`this.multiplicityMetadata.per_instance_params` вместо hardcoded `["width","height"]`.

Само API + helpers MVP — пълна UI integration (per-instance renderer,
widget_hint switch) остава за future iteration.

## [18.0.1.10.0] - 2026-05-25

### Added — TΦ Cascade integration в configurator (Phase A)

- `DesignConfiguratorWidget`:
  - Нов prop `cascadeTable` (Json, optional).
  - `_applyCascade(changedKey, newValue)` — async helper извикан на всяка
    `onParamChange` **преди** `_validate` и TΠ eval. Извиква
    `mrp.bom._configurator_evaluate_cascade(bom_id, changed_param, context)`
    и applies резултата върху `this.params`.
  - Param name resolution: подава DPD `string` ключ (`main_color`) на сървъра,
    обратно резолва `target_param`/`copy_from` от string до hash UUID name.
  - Reentry guard `_cascadeInProgress` (single-pass MVP — multi-step chains
    се правят с повторен user input).
  - `only_if_empty` default true; treats `""`, `null`, `false`, `"use_main"`
    като "empty" → user explicit choice не се overwrite-ва.
- `DesignConfiguratorDialog` чете `cascade_table` от BoM, passes `cascadeTable`
  на widget-а. Defaults на false → когато BoM няма TΦ, widget-ът работи както
  досега.

## [18.0.1.9.0] - 2026-05-24

### Added

- **MTO design_lot_id propagation** (recovered от host hot-fix 4-5 май):
  - `stock.move.design_lot_id` field + `_prepare_procurement_values` override
    forward-ва design_lot_id към upstream MTO procurements (SO → delivery move
    → component move → MO).
  - `mrp.production.design_lot_id` transient inlet field; `_prepare_mo_vals`
    override копира design_lot_id от procurement values в mo_vals.

### Changed

- `sale.order.line` — hybrid integration на host's hot-fix + PR #1 (vladikanchev):
  - Нов helper `_build_design_param_bullets()` — single source-of-truth за
    render-а на design params. Връща `["label: value", ...]` с правилно UUID
    → human label resolution + selection code → display value (host's enriched
    pipeline). Hide rules: empty/False, `"use_main"` sentinel (PR #1),
    `color_X` matching `main_color` (PR #1 dedup).
  - `_compute_design_params_summary` сега reuse-ва `_build_design_param_bullets`
    — UUID hashes стават human labels в kanban/list display (regression fix
    спрямо raw `.items()` от PR #1).
  - `_get_sale_order_line_multiline_description_sale` super-override (host's
    pattern) — append-ва bullet list под product display name в PDF-овете;
    reuse-ва същия bullet pipeline.
  - `_regenerate_design_description` reuse-ва `_build_design_param_bullets`
    вместо да дублира render логиката.
  - Triggers: PR #1's `set_design_lot` + host's `write` override + host's
    `_onchange_design_lot_refresh_name` — всичките викат
    `_regenerate_design_description` за consistency. Broader coverage
    (manual ORM + UI + RPC).

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
