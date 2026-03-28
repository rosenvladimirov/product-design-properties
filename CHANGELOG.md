# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
