Extends `mrp_bom_line_formula_quantity` (OCA) with:

- **Reusable formula templates** — store named formulas in
  `mrp.bom.line.formula.template` and reference them from any BoM line
  via `formula_template_id`.  Editing the template updates all lines
  that use it.

- **Extended formula output** — formulas can assign three variables:

  - `result` (or legacy `quantity`) — the computed quantity
  - `product` — optional product override via `env.ref()`
  - `uom` — optional UoM override via `env.ref()`

  At move creation, the extended output is unpacked via an override of
  `_get_move_raw_values` so the move uses the correct product and UoM.

- **Design context injection** — when the calling code passes a
  `design_context` kwarg (e.g. `mrp_design_matrix` during MO generation)
  the context keys become top-level formula variables (`width`,
  `height`, T1 geometry outputs, etc.) so formulas can reference them
  directly.
