# Changelog

## 19.0.1.2.0 — 2026-04-16

### Fixes

- Propagate `design_lot_id` through the full SO → MO pull chain:
  - `stock.move.design_lot_id` (Many2one) field added — persists on
    the move so the MTO re-derivation can forward it.
  - `stock.move._prepare_procurement_values` override forwards
    `design_lot_id` to upstream procurements.
  - `mrp.production.design_lot_id` (Many2one) transient inlet consumed
    by `MrpProduction.create()` into `lot_producing_ids`.
  - `stock.rule._prepare_mo_vals` override carries `design_lot_id`
    from procurement values into MO create vals.

  Before this fix, the matrix engine silently no-op'd on MTO-triggered
  MOs with "MO has no lot_producing_ids", because the design lot set
  on the SO line never reached the MO.

## 19.0.1.1.0 — 2026-04-16

### Fixes

- Migrate to Odoo 19 `lot_producing_ids` (from `lot_producing_id`
  Many2one). The SO → MO design-lot propagation in `create()` and
  the "Open Configurator" button now use the plural One2many field.

## 19.0.1.0.0 — 2026-03 (initial)

- SO line design configurator with 3D preview for parametric
  manufacturing.
