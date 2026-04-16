# Changelog

## 19.0.1.8.0 — 2026-04-16

### Fixes

- Migrate to Odoo 19 `mrp.production.lot_producing_ids` (was `lot_producing_id`
  Many2one; now One2many). Uses `lot_producing_ids[:1]` as the design lot.
- `stock.lot._get_design_context()` now translates UUID keys → schema
  `string` names and display labels → raw selection values, so T1/T2/T3
  rules match the values stored on the lot.
- `_eval_t0_constraints` accepts both list (zen-engine 0.53+ `collect`
  hit policy) and dict (legacy) return shapes.
- `_create_or_update_matrix_move` writes `stock.move.reference` instead
  of the removed `stock.move.name` field.
- `_unpack_formula_result` calls `_resolve_variant_by_ptav` for O-variant
  BoM lines that define `param_attribute_map`, so the matrix-selected
  move uses the correct product variant from the design context — not
  the static placeholder stored on the BoM line.

### Known issues

- Duplicate move_raw lines: standard MRP and the matrix engine both
  generate moves for the same BoM line. Planned fix in 19.0.1.9.0.
- XML `eval=""` matrix templates (canned_peppers, doors) still use
  Python dict literals that a fresh install reverts to the old zen
  schema. Migration of the XML files is tracked as a separate commit
  in the repo.

## 19.0.1.7.0 — 2026-04-16

### Fixes

- Matrix template JDM migration helper (string → node schema, edges,
  `field` on I/O, wildcard `""` for missing input ids in rules).

## 19.0.1.6.0 — 2026-04-12

### Fixes

- Initial Odoo 19 + zen-engine 0.53 compatibility work (reverted and
  re-done in 19.0.1.7/8.0).

## 19.0.1.0.0 — 2026-03 (initial)

- Parametric BoM driven by lot-level design parameters and a DMN rule
  matrix. T0/T1/T2/T3 tables via GoRules zen-engine.
