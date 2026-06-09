# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [18.0.2.0.0] - 2026-06-09

Major release — kernel extraction, cost-plus pricing engine, six new industry
verticals and the roller-shutter range. Summarises ~99 commits since 1.10.0.

### Added
- **base_zen_decision** — standalone ZEN/GoRules decision-table kernel
  (evaluate + trace + version + sync), extracted from `mrp_design_matrix` and
  now shared with access control.
- **sale_design_pricing** — cost-plus pricing engine: separate material/labor
  markups, vendor pricing, recursive phantom/semi-finished BoM cost walk,
  admin-only price breakdown, Matrix-Template integration.
- New industry verticals: `security_door`, `interior_door`, `smart_display`,
  `roller_garage_door`, `bags`, `canned_peppers`.
- Roller-shutter range (`mrp_design_matrix_shutters`) — 5-model range with T3
  assembly operations, box-capacity (H_MAX) constraints, Thermo-Comfort RAL
  colour restrictions.
- TΦ cascade engine (`derive_expression`, box-by-height lookup) + TΩ/TΛ widget
  API; `mrp.bom.simulate_with_params` live-eval helper.
- 3 modules adopted from Vladimir Kanchev's design pipeline.

### Changed
- `mrp_design_matrix` → 18.0.2.x: Phase 1 kernel extraction; shutters data
  split into work centers + DB-sourced matrix.
- T3 operation `duration_formula` applied to work orders + linked raw moves.
- `sale_design_configurator` — full-viewport 3D dialog.

### Removed
- `teolino_*` customer-specific modules moved to the dedicated `teolino` repo.

### Fixed
- Pricing/matrix/shutters hardening: labor rate = work-center + employee cost,
  T3 duration accounts for `shutter_count`, BoM decision-table fallback from
  matrix template, ZenWrapper import path, XML eval-attr quoting, public RPC
  entry for TΠ availability, and more.

## [18.0.1.10.0] - 2026-05-24

### Added — 3 нови модула от Teolino design pipeline (Vladimir Kanchev)

- **sale_design_pricing** v18.0.1.2.1 — cost-plus pricing engine за parametric
  design products. Separate material/labor markups (configurable per company
  + per product category override). Adds computed fields на sale.order.line
  (cost_material, cost_labor, list_price_material, list_price_labor,
  list_price_total, cost_breakdown_html) + `mrp.bom._evaluate_cost_with_params(params)`.
  Generic (без teolino_ префикс) — приложим за всеки cost-plus design домейн.
  Views temporarily disabled (виж manifest comment — stale view records в
  Vladimir's Odoo build).
- **teolino_mrp_design_recompute** v18.0.1.2.1 — server-side BoM simulation
  engine + auto-recompute hook:
  - `mrp.bom.simulate_with_params(params, qty, per_shutter_pairs=[])` —
    evaluates всеки `quantity_formula` срещу flat params namespace; връща
    breakdown (lines/operations) + totals.
  - `mrp.production.action_confirm` hook → `_teolino_recompute_raw_moves()`
    autо-update на raw move qty след MO confirm. Елиминира нуждата от
    manual `recompute_mo_v2.py`.
  - Резолва design lot чрез lot_producing_id или SO line lookup.
- **teolino_sale_design_configurator_ui** v18.0.1.8.4 — Teolino-specific UI
  overrides на `DesignConfiguratorWidget`:
  - Per-shutter dimension state (L/H array когато shutter_count > 1)
  - Color cascade helpers (main_color → 12 component colors)
  - Color sub-modal (`teolino_color_dialog`) с customer-pickable subset
  - Hardcoded shutter constraints (`teolino_constraints.js` — H_HARD_MAX,
    L_HARD_MAX, BOX_BY_HEIGHT_AND_SLAT)
  - LIVE BoM preview (debounced RPC → `mrp.bom.simulate_for_variant`)
  - Full template override на `sale_design_configurator.DesignConfiguratorWidget`

### Known issues (документирани, без resolve)

- **T1 rules duplication**: `teolino_mrp_design_recompute._T1_RULES` (Python
  dict) дублира `mrp_design_matrix_shutters/data/matrix_templates.xml`
  geometry_table. Single source-of-truth би било XML seed-ът, но prod-ът
  на teolinobisness.com има zen-engine pip package, който не работи (TBD
  causes). Дотогава Python hardcode е runtime fallback. **Drift риск**:
  всяка промяна на T1 правилата в XML трябва ръчно да се огледа и тук.
- **TΠ Availability UI override**: когато `teolino_sale_design_configurator_ui`
  е installed, неговото teolino_dialog.xml пълно override-ва template-а на
  upstream `DesignConfiguratorWidget` → моят TΠ reactive disable
  (`tpiEnabled`/`o_cfg_disabled`) **не работи в UI**. Teolino-specific
  constraints се покриват от `teolinoFiltered()` hardcoded JS rules. TΠ
  data остава полезен за generic модули (без custom UI override) и за
  server-side проверки.

## [18.0.1.7.5] - 2026-05-04

### Fixed

- **sale_design_configurator** (18.0.1.6.0) — Human-readable design params in
  SO line summary + auto-append to description (folded in from
  `sale_design_configurator_summary_fix` v18.0.1.0.0):
  - `_compute_design_params_summary` now reads through
    `lot.read(['design_params'])` so the properties framework merges template
    + definition metadata; selection values are resolved to their human label
    instead of leaking the internal code.
  - New `_get_sale_order_line_multiline_description_sale` override appends
    the summary as a bullet list under the SO line `name` — visible in form,
    PDF report, and downstream invoice.
  - New `write` and `_onchange_design_lot_refresh_name` keep the SO line
    `name` in sync whenever `design_lot_id` changes (live UI refresh + ORM
    write path).
- **design_param_base** (18.0.1.0.4) — `design_param_definition` form view:
  `widget="json"` (does not exist in v18) replaced by
  `widget="ace" options="{'mode': 'json'}"` on `validation_rules`; same widget
  added to `design_params_definition` so the *Parameter Definitions* tab is
  no longer blank.

## [18.0.1.7.4] - 2026-04-29

### Fixed

- **mrp_design_matrix** (18.0.1.7.1) — MatrixPreviewDialog scroll fix:
  grid layout uses `height: clamp(500px, 65vh, 900px)` instead of `max-height`;
  both panels get `min-height: 0` so grid children can scroll properly;
  right panel changed to `overflow-y: hidden` — inner `RuleMatrixPreview` owns the scroll.

## [18.0.1.7.3] - 2026-04-29

### Added

- **mrp_design_matrix_roller_door** (18.0.1.3.0) — GLB 3D models for Three.js viewer:
  two converted STL→GLB files (shutter assembly + box assembly) in `static/models/`;
  `post_init_hook` links them to the demo product via `design_asset_ids`
  when `product_design_assets` is installed.

## [18.0.1.7.2] - 2026-04-29

### Added / Changed

- **mrp_design_matrix_roller_door** (18.0.1.2.0) — full T0/T1/T2/T3 matrix
  from Excel BoM reference; box_size 205 added; complete demo BoM with 20 lines
  (formula-driven + O-variants for motor/crank/insulation/mosquito).

## [18.0.1.7.1] - 2026-04-29

### Added

- **mrp_design_matrix_roller_garage_door** (18.0.1.0.0) — new industry module:
  7 design params, full T0/T1/T2/T3 template, demo BoM with formula lines
  and 3 O-variants (motor / side seals / wicket door).

## [18.0.1.7.0] - 2026-04-29

### Fixed

- **mrp_design_matrix** (18.0.1.7.0) — zen-engine >=0.50 compatibility:
  legacy node type migration, `field` injection, bare-table wrapping,
  `hitPolicy: collect` list output normalization.
- **design_param_base** (18.0.1.0.3) — coerce XML `default` string to
  declared type (integer/float/boolean) to prevent Owl widget crashes.
- **mrp_design_matrix_corrugated** (18.0.1.1.0) — full T0/T1/T2/T3 matrix
  template for RSC corrugated boxes (was empty `eval="{}"`).

## [18.0.1.6.0] - 2026-04-02

### Added
- **mrp_design_matrix** (18.0.1.2.0) — `DesignMatrixField` OWL widget (Phase 1+2: read-only + edit)
  - Visual DMN decision table renderer for GoRules JDM JSON fields
  - Replaces ACE JSON editor in BoM form for T0/T1/T2/T3 tables
  - Input columns (blue) / output columns (green) grid layout
  - hitPolicy badge (COLLECT / FIRST / PRIORITY)
  - Collapsible sections with rule count
  - Error/warning level badges for T0 constraint outputs
  - Smart cell formatting: wildcards, booleans, operators, JSON objects

*Assisted by Claude Code*

## [18.0.1.5.0] - 2026-03-30

### Added
- **product_design_assets** (18.0.1.1.0) — `get_template_variant_assets()` RPC
  - Returns all variants of a product template with their PNG/JPG textures
  - Used by overlay gallery to show all selectable accessory variants

### Changed
- **sale_design_configurator** (18.0.1.2.0) — Sliding overlay panel with variant gallery
  - Bottom-anchored overlay panel (90% transparent, frosted glass) over 3D viewport
  - Drag handle for resizing — click to toggle, drag to adjust height
  - Auto-generated description from current parameter selections
  - Accessory gallery shows ALL variants per component (lock, handle) with click-to-select
  - Active variant highlighted with Odoo purple border
  - Selected accessories stored in `design_params._selected_accessories`
  - Overlay opens automatically when accessory variants are available
  - Removed hotspot spheres, SVG connector lines and popup (replaced by overlay)

*Assisted by Claude Code*

## [18.0.1.3.0] - 2026-03-28

### Added
- **product_design_assets** (18.0.1.0.0) — New module linking product attachments to design visualization
  - `product.product.get_design_assets_by_type()` RPC — groups attachments by mimetype (GLB/SVG/PNG)
  - `mrp.bom.get_bom_design_assets()` RPC — returns design assets for all BoM line products
  - Smart button "Design Assets" on product form
  - Automatic detection: model/gltf-binary → 3D, image/svg+xml → profile, image/* → texture

### Changed
- **sale_design_configurator** — GLB 3D model rendering from BoM product attachments
  - New `_buildFromBomAssets()` Three.js method loads GLB via GLTFLoader
  - Auto-applies texture from same product's PNG/JPG attachment
  - Auto-center + auto-scale for any model size
  - Priority: bomAssets GLB → SVG profiles → legacy builders (fallback)
  - Added `GLTFLoader.js` (Three.js r128) to assets bundle
  - Depends on `product_design_assets`

*Assisted by Claude Code*

## [18.0.1.2.0] - 2026-03-28

### Added
- **mrp_bom_line_formula_template** (18.0.1.0.0) — Ported from 19.0 to 18.0
  - Reusable formula templates for BoM line quantities
  - `mrp.bom.line.formula.template` model with syntax validation
  - `formula_template_id` on BoM line — select template, formula auto-fills
  - Menu under MRP > Configuration > BoM Line Formula Templates
- **mrp_bom_line_formula_wizard** (18.0.1.0.0) — New formula editor wizard
  - Replaces inline text column with a dedicated popup editor
  - `widget=code` for Python syntax highlighting
  - Available variables reference panel in the wizard
  - Apply / Clear / Cancel buttons
  - `fa-code` button in BoM line list opens the wizard

## [18.0.1.1.0] - 2026-03-28

### Added
- **design_param_base** (18.0.1.0.0) — New shared module for `design.param.definition` model
  - `design.param.profile` model with SVG content + JSON profile definitions
  - `validation_rules` Json field for data-driven client-side validation
  - `company_ids` Many2many for per-company filtering
  - `mrp.bom` extension with `design_param_definition_id`
- **stock_lot_properties** (18.0.1.0.0) — New module for lot-level Properties
  - `stock.lot.design_param_definition_id` + `design_params` (Properties field)
  - Lot form view with "Design Parameters" tab
- **sale_design_configurator** (18.0.1.0.0) — SO line design configurator
  - OWL widget with Three.js 3D preview (security_door, interior_door, bags, roller_door, corrugated)
  - Data-driven validation from `validation_rules` JSON with generic condition evaluator
  - SVG profile rendering via SVGLoader + ExtrudeGeometry (primary) with legacy fallback
  - `res.config.settings` for per-company definition selection
  - Auto-open configurator on product selection (SaleOrderLineProductField patch)
  - SO line → lot → MO propagation via procurement values
- **mrp_design_matrix** (18.0.1.0.0) — Core parametric BoM engine
  - T0/T1/T2/T3 DMN rule evaluation via GoRules ZEN engine
  - O-variant coefficient pattern (coeff=0.0 for planning, coeff>0.0 for execution)
  - PTAV resolution (design param → product attribute → variant)
  - Semi-finished goods: child lot creation with param_extraction_map
  - MTO stop logic with stock lot matching
- **mrp_design_matrix_bags** (18.0.1.0.0) — Garbage bag manufacturing
- **mrp_design_matrix_corrugated** (18.0.1.0.0) — Corrugated boxes + board
- **mrp_design_matrix_roller_door** (18.0.1.0.0) — Roller shutters
- **mrp_design_matrix_security_door** (18.0.1.0.0) — Security doors (RC class logic)
- **mrp_design_matrix_interior_door** (18.0.1.0.0) — Interior doors
- **mrp_design_matrix_smart_display** (18.0.1.0.0) — Smart home display panels
  - 30 design parameters (display, platform, connectivity, housing, sensors, audio, branding)
  - T0: ESP32 limits, USB-C power constraints, antenna isolation
  - T2: 12 O-variant activations; T3: 6 conditional operations
- **mrp_design_matrix_canned_peppers** (18.0.1.0.0) — Canned roasted peppers
  - 32 design parameters (recipe, container, lid, label, packaging, palletizing)
  - T0: stuffed+small jar, tin+twist-off, ajvar+vinegar constraints
  - T2: 18 O-variant activations; T3: 5 conditional operations

### Changed
- Unified `design.param.definition` model — replaces duplicate `mrp.design.param.definition`
- All industry submodules now reference `design.param.definition` (was `mrp.design.param.definition`)
- Dependency graph restructured:
  ```
  design_param_base → stock_lot_properties → sale_design_configurator
                                           → mrp_design_matrix → industry submodules
  ```

### Documentation
- README.md with full architecture overview, module stack diagram, data models
- docs/BRD.md — Business Requirements Document (English)
- docs/SRD.md — System Requirements Document (English)
- docs/PROJECT_PLAN.md — Project Plan with phases and timeline (English)

*Assisted by Claude Code*
