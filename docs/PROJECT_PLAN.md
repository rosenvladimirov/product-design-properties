# MRP Design Matrix — Project Plan

**Version:** 2.0 | **Last revision:** 2026-04-05 | **Author:** Rosen Vladimirov \<vladimirov.rosen@gmail.com\> | Terraros Commerce Ltd.

---

## Scope and Objective

Development and publication in OCA of a stack of Odoo 18 modules for design-driven manufacturing. The project includes the core (generic engine), five+ industry sub-modules, a 3D SO configurator, and AI-assisted formula generation.

**End result:** PR in `OCA/manufacture` and `OCA/stock-logistics-workflow` + production-ready deployment.

---

## Phase 0 — Foundation (2 weeks)

Preparation of existing modules for OCA publication.

| Task | Module | Priority | Status |
|---|---|---|---|
| PR: `stock_move_forced_lot_multi` | stock-logistics-workflow | Critical | External (OCA) |
| PR: `stock_move_forced_lot_multi_dim` | stock-logistics-workflow | Critical | External (OCA) |
| Tests for forced lot propagation | the above | Critical | **TODO** |
| OCA pre-commit setup for the new repo | `mrp_design_matrix` | High | **TODO** |

**Key result:** forced_lot PRs in OCA — everything else depends on them.

---

## Phase 1 — The Bridge (1 week) — **REDESIGNED**

Original plan: a separate `mrp_bom_formula_lot_dimension` module.
**Actual:** merged into `mrp_bom_line_formula_template` as a more powerful formula system.

| Task | Location | Status |
|---|---|---|
| `_quantity_formula_values` override with design context | `mrp_bom_line_formula_template/models/mrp_bom_line.py` | ✓ Done |
| `env` exposed in formula globals | same | ✓ Done |
| Extended output: `result`, `product`, `uom` | same | ✓ Done |
| `_get_move_raw_values` unpacks result dict | `mrp_bom_line_formula_template/models/mrp_production.py` | ✓ Done |
| Tests — formula uses `width` and `bag_type` from lot Properties | — | **TODO** |

**Key result:** `quantity_formula` sees all design_params + can override product/UoM at MO creation.

---

## Phase 2 — Core: Models (2 weeks) — **DONE**

| Task | Description | Status |
|---|---|---|
| `design.param.definition` | PropertiesDefinition + XML parser + inheritance chain | ✓ (in `design_param_base`) |
| `mrp.matrix.template` | 4× JSON fields, basic CRUD | ✓ |
| `mrp.bom` extension | `design_param_definition_id`, 4× JSON tables, `action_load_from_template()` | ✓ |
| `mrp.bom.line` extension | `coeff_default`, `matrix_coeff_rule`, `param_attribute_map`, `param_extraction_map`, `child_definition_id`, `mto_stop` | ✓ |
| `stock.lot` extension | `design_param_definition_id` + `design_params` Properties | ✓ (in `stock_lot_properties` + helpers in `mrp_design_matrix`) |
| `design_matrix` OWL widget | Replaces ACE JSON editor — visual DMN table | ✓ (v18.0.1.4.0) |

**Bonus (not in original plan):**
- ✓ Matrix Preview dialog on BoM form — live T0/T1/T2/T3 simulation
- ✓ JSON↔Table toggle, hitPolicy selector, drag-reorder
- ✓ Smart cell encoding/decoding (no manual quoting)

**Key result:** all models in place, UI allows matrix configuration, live preview available.

---

## Phase 3 — Core: Logic (2 weeks) — **DONE (except tests)**

| Task | Location | Status |
|---|---|---|
| GoRules wrapper class | `mrp_design_matrix/models/zen_engine.py` | ✓ |
| `_generate_design_matrix_moves()` | `mrp_design_matrix/models/mrp_production.py` | ✓ |
| `_resolve_t2_product()` (Type 1/2/3 dispatch) | same | ✓ |
| `_resolve_variant_by_ptav()` | same | ✓ |
| `_create_child_lot()` with `param_extraction_map` | `mrp_design_matrix/models/stock_lot.py` | ✓ |
| `_find_matching_stock_lot()` | same | ✓ |
| `mto_stop` branching | `mrp_production.py:_handle_semifinished_lots` | ✓ |
| Integration tests — at least 5 covering main paths | — | **TODO** |

**Key result:** full MO algorithm works end-to-end. Tests are the only missing piece.

---

## Phase 4 — Industry Sub-modules (3 weeks) — **DONE (7 modules instead of 5)**

| Sub-module | XML definitions | JSON templates | Demo BoM | Status |
|---|---|---|---|---|
| `mrp_design_matrix_bags` | ✓ | ✓ | ✓ | Complete |
| `mrp_design_matrix_corrugated` | ✓ | ✓ | ✓ | Complete |
| `mrp_design_matrix_roller_door` | ✓ | ✓ | ✓ | Complete |
| `mrp_design_matrix_security_door` | ✓ | ✓ | ✓ | Complete |
| `mrp_design_matrix_interior_door` | ✓ | ✓ | ✓ | Complete |
| `mrp_design_matrix_canned_peppers` | ✓ | ✓ | ✓ | Complete (bonus) |
| `mrp_design_matrix_smart_display` | ✓ | ✓ | ✓ | Complete (bonus) |

**Missing:** per-module `README.rst` and `CHANGELOG.md` — see Phase 5.

---

## Phase 5 — Finalization and OCA (1 week) — **PARTIAL**

| Task | Status |
|---|---|
| Code review and cleanup (`ruff`, `black`, OCA checks) | **TODO** |
| Per-module `README.rst` | **TODO** (root `README.md` exists) |
| Per-module `CHANGELOG.md` | Partial — core modules have it, sub-modules do not |
| Demo data on fresh installation | ✓ (demo_bom_*.xml in every sub-module) |
| PR to `OCA/manufacture` + `OCA/stock-logistics-workflow` | **TODO** |

---

## Phase 6 — Beyond the original plan — **DONE**

Additional modules and features added during development.

| Module | Version | Purpose |
|---|---|---|
| `design_param_base` | 18.0.1.0.0 | Shared parameter definitions, schema validation, inheritance |
| `stock_lot_properties` | 18.0.1.0.0 | `stock.lot` Properties fields (split from mrp_design_matrix for reuse) |
| `product_design_assets` | 18.0.1.1.0 | GLB / SVG / PNG / DXF assets on product variants |
| `sale_design_configurator` | 18.0.1.5.0 | SO line 3D configurator (Three.js r128), lot creation flow, RuleMatrixPreview fallback |
| `mrp_bom_line_formula_template` | 18.0.1.1.0 | **Replaces** the Phase 1 bridge — formula templates + extended `result/product/uom` |
| `mrp_bom_line_formula_wizard` | 18.0.1.1.0 | Wizard UI for formula editing with template picker |
| `mrp_bom_line_formula_claude` | 18.0.1.0.0 | Claude AI assistant in wizard (MCP + iframe + live refresh) |

---

## Phase 7 — Production Readiness (NEW) — **IN PROGRESS**

Tasks to bring the whole stack to a deployable production state.

### 7.1 Quality Gates
- [ ] Add `.pre-commit-config.yaml` at repo root (OCA standard)
- [ ] Add `pyproject.toml` with ruff/black config
- [ ] Run `pre-commit run -a` — fix all findings
- [ ] Run Odoo `manifestoo` — verify no missing dependencies
- [ ] Run OCA's `oca-gen-addon-readme` for each module

### 7.2 Tests (blocking for production)
- [ ] `mrp_design_matrix` — T0/T1/T2/T3 evaluation unit tests
- [ ] `mrp_design_matrix` — MO integration test (5+ scenarios)
- [ ] `mrp_design_matrix` — PTAV resolution test
- [ ] `mrp_design_matrix` — mto_stop / _find_matching_stock_lot test
- [ ] `mrp_design_matrix` — _create_child_lot test with safe_eval extraction
- [ ] `mrp_bom_line_formula_template` — extended formula eval (result/product/uom)
- [ ] `design_param_base` — definition inheritance + XML parser test
- [ ] `sale_design_configurator` — SO line → design lot → MO lot propagation
- [ ] Sub-modules — smoke test per module (install + demo BoM loads)

### 7.3 Documentation
- [ ] `README.rst` per module (OCA standard, auto-generated from fragments)
- [ ] `CHANGELOG.md` per sub-module
- [ ] User guide: "How to build a new industry sub-module in 30 minutes"
- [ ] Developer guide: T0/T1/T2/T3 matrix authoring
- [ ] Update root `README.md` with architecture diagram + module graph

### 7.4 Security & Multi-company
- [ ] Review `ir.model.access.csv` in every module
- [ ] Check record rules on `stock.lot.design_params` (multi-company isolation)
- [ ] Verify `design_param_definition_id.company_ids` filters correctly
- [ ] Audit `safe_eval` usage in `_create_child_lot` + formulas (restricted globals)
- [ ] Verify no `sudo()` escapes in matrix evaluation path

### 7.5 Performance
- [ ] Benchmark `_generate_design_matrix_moves` on a 50-line BoM with T0+T1+T2+T3
- [ ] Cache `ZenWrapper.evaluate` results per (table_hash, context_hash) in MO transaction
- [ ] Verify ORM prefetch for `bom_line_ids` + `product_id` in the moves loop
- [ ] Profile SVG/GLB loading in `sale_design_configurator` on slow networks

### 7.6 Data Migration
- [ ] Migration script: existing BoMs without `design_param_definition_id`
- [ ] Migration script: existing lots without `design_params` Properties
- [ ] Fallback path when `zen-engine` Python package is not installed
- [ ] Version bump strategy documented (semantic versioning per module)

### 7.7 Deployment
- [ ] Docker Compose reference for the MCP stack (already in `odoo-claude-mcp`)
- [ ] Ansible/playbook for production deploy
- [ ] Per-client branch strategy (source → demo → client)
- [ ] Rollback procedure documented

### 7.8 OCA Submission
- [ ] Early precheck with OCA/manufacture maintainer
- [ ] PR: `stock_move_forced_lot_multi` (Phase 0, prerequisite)
- [ ] PR: `mrp_bom_line_formula_template` (formula extension)
- [ ] PR: `design_param_base` + `stock_lot_properties` (foundation layer)
- [ ] PR: `mrp_design_matrix` (core engine)
- [ ] PR: industry sub-modules (one per sub-module)
- [ ] PR: `sale_design_configurator` (optional — sale integration)

---

## Summary Timeline

| Phase | Original | Actual Status |
|---|---|---|
| Phase 0 — Foundation | 2 weeks | External, test TODO |
| Phase 1 — Bridge | 1 week | ✓ Redesigned as formula template |
| Phase 2 — Models | 2 weeks | ✓ Complete + bonus features |
| Phase 3 — Logic | 2 weeks | ✓ Complete (no tests) |
| Phase 4 — Sub-modules | 3 weeks | ✓ Complete (7/5 modules) |
| Phase 5 — OCA | 1 week | Partial (docs + tests blocking) |
| Phase 6 — Beyond plan | — | ✓ 7 extra modules |
| Phase 7 — Production | — | **In progress** |

---

## Risks (updated)

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| OCA review requires substantial changes | Medium | High | Early precheck with maintainer (Phase 7.8) |
| GoRules does not cover all T0 cases | Low | Medium | cDMN fallback (not yet needed) |
| Properties engine changes in Odoo 18.x | Low | High | Tests on every minor version (Phase 7.2) |
| PTAV matching requires exact name correspondence | High | Medium | Validation + unit tests (Phase 7.2) |
| Industry templates incomplete | Medium | Low | Demo data + developer guide (Phase 7.3) |
| `zen-engine` package unavailable in target env | Medium | High | Bundling strategy + fallback (Phase 7.6) |
| Multi-company data leakage via design_params | Low | Critical | Security audit (Phase 7.4) |
| Formula `safe_eval` bypass | Low | Critical | Restricted globals audit (Phase 7.4) |

---

## Dependencies (updated)

**External (OCA):**
- ~~`mrp_bom_line_formula_quantity`~~ — replaced by own core in `mrp_bom_line_formula_template`
- `stock_move_forced_lot_multi` — PR needed (Phase 0)
- `stock_move_forced_lot_multi_dim` — PR needed (Phase 0)

**External (PyPI):**
- `zen-engine` — GoRules JDM evaluator (1 line `pip install`, no transitive deps)

**Internal (this repo, in load order):**
```
design_param_base
stock_lot_properties
product_design_assets
mrp_bom_line_formula_template
mrp_bom_line_formula_wizard
mrp_bom_line_formula_claude   (needs l10n_bg_claude_terminal)
mrp_design_matrix
  └── mrp_design_matrix_bags
  └── mrp_design_matrix_corrugated
  └── mrp_design_matrix_roller_door
  └── mrp_design_matrix_security_door
  └── mrp_design_matrix_interior_door
  └── mrp_design_matrix_canned_peppers
  └── mrp_design_matrix_smart_display
sale_design_configurator
```

---

## Definition of Done (production)

### For OCA submission (Phase 5)
- [ ] All tests pass (pytest, no skips)
- [ ] pre-commit: `ruff`, `black`, OCA checks — no errors
- [ ] `README.rst` filled in for each module
- [ ] Changelog up to date
- [ ] Demo data works on fresh installation
- [ ] PR description contains context, screenshots, test instructions

### For production deployment (Phase 7)
- [ ] All OCA DoD items above
- [ ] Security audit passed (multi-company + safe_eval)
- [ ] Performance benchmarks documented
- [ ] Migration scripts tested on real customer data
- [ ] Deployment runbook tested end-to-end
- [ ] Rollback procedure verified
- [ ] At least one production customer running for 30 days without blocker bugs

---

## Current TODO (priority order)

**Blocking for production:**
1. Integration tests for `_generate_design_matrix_moves` (Phase 7.2)
2. Security audit of `safe_eval` and multi-company (Phase 7.4)
3. pre-commit + ruff/black clean run (Phase 7.1)
4. Migration scripts for existing BoMs/lots (Phase 7.6)

**Blocking for OCA PR:**
5. `README.rst` per module (Phase 7.3)
6. `CHANGELOG.md` per sub-module (Phase 7.3)
7. OCA maintainer precheck (Phase 7.8)

**Nice to have:**
8. Performance benchmarks + caching (Phase 7.5)
9. Developer guide (Phase 7.3)
10. Ansible deployment playbook (Phase 7.7)
