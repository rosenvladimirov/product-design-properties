Embeds a live design configurator on Sale Order lines for products
linked to a `design.param.definition`.  When a salesperson picks a
configurable product, a modal opens with:

- **Left panel** — parameter controls (sliders, segmented buttons,
  checkboxes) generated from the design parameter definition.
- **Right panel** — 3D viewport (Three.js r128) loading GLB models
  and SVG profiles from `product_design_assets`, or a
  `RuleMatrixPreview` fallback when the product has no visual assets
  but does have matrix tables.

On confirmation the configurator creates a `stock.lot` carrying the
chosen `design_params`, links it to the SO line via `design_lot_id`,
and propagates it to the MO via `lot_producing_id` at confirmation
time.  The `mrp_design_matrix` engine then uses those parameters to
drive T0/T1/T2/T3 evaluation.
