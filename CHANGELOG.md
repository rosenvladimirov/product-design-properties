# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **base_formula_engine** (1.0.0) — new domain-agnostic formula kernel
  - `formula.engine.mixin`: syntax validation + safe_eval exec with a
    declared-outputs contract and opt-in `strict` mode (payroll-grade
    hard fail); `_formula_eval_context` extension hook
  - `formula.template`: reusable multi-company formula records with
    `code` lookup (company record wins over global), per-company AND
    global uniqueness (partial unique index)
  - Port of the 19.0 module (feat/base-formula-engine); same code —
    safe_eval package re-exports and orm table objects verified on 20

### Added
- **mrp_design_matrix_solid_door** (19.0.1.0.0) — new industrial submodule
  - Properties definition for SolidDoor product range (portalsolid.com)
  - 18 door models, coating/frame/slab/line/handle/lock/extras parameters
  - Matrix template ``Solid Door — Standard`` (T0/T1/T2/T3 GoRules JDM)
  - Workcenters: SDMILL, SDASM, SDFIN, SDFIRE, SDFRM

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
