**Create a template:**

1.  Go to _Manufacturing → Configuration → Formula Templates_.
2.  Click _New_, enter a name and the formula body.
3.  Available input variables:

    - `bom_line`, `production`, `product`, `product_uom`,
      `product_uom_qty`, `operation`
    - `env` — Odoo environment
    - Design context keys (`width`, `height`, …) when called from
      `mrp_design_matrix`

4.  Output: assign to `result` (or `quantity`).  Optionally assign
    `product` / `uom` to override the BoM line's defaults.

**Reference from a BoM line:**

1.  Open a BoM, edit a line.
2.  Set _Formula Template_ to the desired template.
3.  The line's `quantity_formula` is populated automatically.

**Example:**

```python
# Weight-based quantity with product override
result = (width / 1000) * (height / 1000) * density
if material == "steel":
    product = env.ref("my_module.steel_sheet")
    uom = env.ref("uom.product_uom_kgm")
```
