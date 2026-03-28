# MRP Design Matrix — Project Plan

**Version:** 1.0 | **Date:** March 2026 | **Author:** Rosen Vladimirov \<vladimirov.rosen@gmail.com\> | BL Consulting | Odoo Silver Partner

---

## Scope and Objective

Development and publication in OCA of a stack of Odoo 18 modules for design-driven manufacturing. The project includes the core (generic engine) and five industry sub-modules.

**End result:** PR in `OCA/manufacture` and `OCA/stock-logistics-workflow`.

**Total duration:** ~11 weeks

---

## Phase 0 — Foundation (2 weeks)

Preparation of existing modules for OCA publication.

| Task | Module | Priority | Effort |
|---|---|---|---|
| PR: `stock_move_forced_lot_multi` | stock-logistics-workflow | Critical | 3 days |
| PR: `stock_move_forced_lot_multi_dim` | stock-logistics-workflow | Critical | 1 day |
| Tests for forced lot propagation | the above | Critical | 2 days |
| OCA pre-commit setup for the new repo | `mrp_design_matrix` | High | 0.5 days |

**Key result:** forced_lot PRs in OCA — everything else depends on them.

---

## Phase 1 — The Bridge (1 week)

`mrp_bom_formula_lot_dimension` — the critical module on which the entire formula logic depends.

| Task | Description | Effort |
|---|---|---|
| `_quantity_formula_values` override | Adds lot dims and Properties flatten to the context | 1 day |
| Tests | Formula uses `width` and `bag_type` from lot Properties | 1 day |
| README + changelog | OCA standard | 0.5 days |

**Key result:** `quantity_formula` sees all design_params without additional code.

---

## Phase 2 — Core: Models (2 weeks)

| Task | Description | Effort |
|---|---|---|
| `mrp.design.param.definition` | PropertiesDefinition + XML parser | 2 days |
| `mrp.matrix.template` | 4x JSON fields, basic CRUD | 1 day |
| `mrp.bom` extension | `design_param_definition_id`, 4x JSON, `action_load_from_template()` | 2 days |
| `mrp.bom.line` extension | `coeff_default`, `matrix_coeff_rule`, `param_attribute_map`, `param_extraction_map`, `child_definition_id`, `mto_stop` | 2 days |
| `stock.lot` extension | `design_param_definition_id` + `design_params` Properties | 1 day |
| `ace_editor` widget | JSON editor in BoM form for the 4 tables | 2 days |

**Key result:** all models are in place, UI allows matrix configuration.

---

## Phase 3 — Core: Logic (2 weeks)

| Task | Description | Effort |
|---|---|---|
| GoRules wrapper class | Loads JSONB, `evaluate()`, error handling | 1 day |
| `_generate_design_matrix_moves()` | T0/T1 chain, the main algorithm | 3 days |
| `_resolve_t2_product()` | Type 1/2/3 dispatch | 1 day |
| `_resolve_variant_by_ptav()` | PTAV matching logic | 2 days |
| `_create_child_lot()` | `param_extraction_map` with copy and `safe_eval` | 2 days |
| `_find_matching_lot()` | Stock matching by `design_params` | 1 day |
| `mto_stop` logic | Branching in `_generate_design_matrix_moves` | 1 day |
| Integration tests | At least 5 tests covering the main paths | 3 days |

**Key result:** full MO algorithm works end-to-end with tests.

---

## Phase 4 — Industry Sub-modules (3 weeks)

| Sub-module | XML definitions | JSON templates | Tests | Effort |
|---|---|---|---|---|
| `mrp_design_matrix_bags` | `bag_type, has_tie, density...` | standard, with_print | 2 | 3 days |
| `mrp_design_matrix_corrugated` | `board_type, grammage...` | BC standard, single wall | 2 | 3 days |
| `mrp_design_matrix_roller_door` | `slat_type, drive_type...` | manual, electric | 2 | 4 days |
| `mrp_design_matrix_security_door` | `RC_class, sheet_thickness...` | RC2, RC3, RC4 | 3 | 4 days |
| `mrp_design_matrix_interior_door` | `construction, opening...` | HDF standard, solid premium | 2 | 3 days |

**Key result:** each sub-module is installable, with demo data and working templates.

---

## Phase 5 — Finalization and OCA (1 week)

| Task | Description | Effort |
|---|---|---|
| Code review and cleanup | `ruff`, `black`, OCA checks — zero errors | 2 days |
| Documentation | `README.rst` for each module | 2 days |
| PR submission | `OCA/manufacture` + `OCA/stock-logistics-workflow` | 1 day |
| Demo data | `demo_bom_*.xml` for each sub-module | 1 day |

---

## Summary Timeline

| Phase | Duration | Key Result |
|---|---|---|
| Phase 0 — Foundation | 2 weeks | forced_lot PR in OCA |
| Phase 1 — Bridge | 1 week | formula module sees Properties |
| Phase 2 — Models | 2 weeks | All models + UI |
| Phase 3 — Logic | 2 weeks | Full MO algorithm |
| Phase 4 — Sub-modules | 3 weeks | 5 industry packages |
| Phase 5 — OCA | 1 week | PR submitted |
| **TOTAL** | **11 weeks** | **~3 months** |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| OCA review requires substantial changes | Medium | High | Early precheck with OCA maintainer |
| GoRules does not cover all T0 cases | Low | Medium | cDMN as fallback for constraints |
| Properties engine changes in Odoo 18.x | Low | High | Tests on every minor version |
| PTAV matching requires exact name correspondence | High | Medium | Validation on `design_params` save |
| Industry templates are incomplete | Medium | Low | Demo data + documentation for extension |

---

## Dependencies

- `mrp_bom_line_formula_quantity` — already in OCA, only version compatibility
- `stock_move_forced_lot_multi` — PR needed **before Phase 3**
- `zen-engine` — `pip install`, no additional dependencies
- `product_electrical_properties` — only a conceptual model, **not a runtime dependency**

---

## Definition of Done (DoD)

- [ ] All tests pass (pytest, no skips)
- [ ] pre-commit: `ruff`, `black`, OCA checks — no errors
- [ ] `README.rst` filled in for each module
- [ ] Changelog (towncrier) up to date
- [ ] Demo data works on fresh installation
- [ ] PR description contains context, screenshots, and test instructions

---

## TODO (current status)

- [ ] Phase 0: PR `stock_move_forced_lot_multi`
- [ ] Phase 0: PR `stock_move_forced_lot_multi_dim`
- [ ] Phase 1: `mrp_bom_formula_lot_dimension` — bridge
- [ ] Phase 2: `mrp.design.param.definition` model + XML parser
- [ ] Phase 2: `mrp.matrix.template` model
- [ ] Phase 2: `mrp.bom` extension + `action_load_from_template()`
- [ ] Phase 2: `mrp.bom.line` extension (all new fields)
- [ ] Phase 2: `stock.lot` extension + Properties
- [ ] Phase 2: `ace_editor` widget
- [ ] Phase 3: GoRules wrapper class
- [ ] Phase 3: `_generate_design_matrix_moves()`
- [ ] Phase 3: `_resolve_variant_by_ptav()`
- [ ] Phase 3: `_create_child_lot()` + `_find_matching_lot()`
- [ ] Phase 4: sub-modules bags / corrugated / roller_door / security_door / interior_door
- [ ] Phase 5: PR → OCA
