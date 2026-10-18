# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.3.5] - 2026-10-18

### Added

First 19.0 release, functionally equal to 18.0.1.3.5 that runs in production:

- Material and labor markups on the company (Settings), the product
  category and the product template, with the effective value on the
  template.
- The order line computes material cost, labor cost and the cost-plus list
  price from the design lot through the BoM (T0–T3 of the BoM or of its
  matrix template, formula quantities with losses, T3 or routing
  operations), uses it as the display price and shows a breakdown to
  administrators.
- `stock.lot.teolino_per_shutter_dims` and `teolino_get_per_shutter_pairs()`.
- After the configurator saves the lot, the line description is rebuilt
  with per-shutter dimensions instead of flat width/height.

### Changed (against 18.0)

- Formula and T3 duration evaluation use the 19.0 `safe_eval` API; T3
  durations go through `safe_eval` like the MO does in mrp_design_matrix.
- The workcenter employee rate is added only when `mrp_workorder` (EE)
  provides `employee_costs_hour`.
- The cost breakdown escapes names and its labels are translatable; the
  line description reuses the bullets of sale_design_configurator and its
  dimension line is translatable.
- UI strings are in English, with a Bulgarian translation.
- The parameter namespace falls back to the stored lot parameters
  (`stock.lot._get_stored_properties()`), not to the 19.0 Properties labels.
