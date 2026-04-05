Core engine for design-driven manufacturing.  Turns a parametric BoM
into a concrete Manufacturing Order by evaluating four GoRules DMN
tables (T0/T1/T2/T3) against a flat design context gathered from the
production lot:

- **T0 — Constraints** (`constraint_table`) — blocks or warns on
  invalid parameter combinations (e.g. "height < 1900 mm" →
  `level=error`).
- **T1 — Geometry** (`geometry_table`) — computes derived dimensions
  and forced values (e.g. `door_weight_kg_m2`, `min_thickness_mm`)
  that become available to T2/T3 and BoM line formulas.
- **T2 — Materials** (`material_table`) — the bill-of-material
  composition.  Supports three row types:

  1.  _Coefficient_ — adjusts a standard BoM line's quantity via
      `matrix_coeff_rule` lookup.
  2.  _Direct ref_ — adds an ad-hoc move for an externally referenced
      product.
  3.  _PTAV_ — resolves a product variant by matching design parameter
      values against `product.template.attribute.value.name`.

- **T3 — Operations** (`operation_table`) — conditional workorders
  that are added only when their activation rule matches.

The engine is stateless — it reads the matrix JSON from the BoM and
the design context from the lot, then generates raw moves and
workorders on the MO.  No caching, no side effects outside of
`stock.move` and `mrp.workorder` creation.

Complementary features:

- **`DesignMatrixField`** — OWL widget that replaces the ACE JSON
  editor with a visual DMN table (read-only + edit mode, JSON↔Table
  toggle, hitPolicy selector, drag-reorder).
- **Matrix Preview** — smart button on the BoM form that opens a
  dialog with parameter controls and live T0/T1/T2/T3 evaluation for
  rapid iteration without creating real MOs.
- **Semi-finished chain** — `child_definition_id` + `mto_stop` let a
  BoM line either spawn a child lot (new MO) or search existing stock
  lots by design parameters (MTO stop).
