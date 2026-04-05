Provides a modal wizard for editing BoM line quantity formulas with:

- **Code widget** — syntax-highlighted Python editor
- **Inline reference** — read-only help panel listing all available
  input and output variables, including design context keys and the
  extended output (`result`, `product`, `uom`)
- **Load from Template** — dropdown to populate the formula from a
  saved `mrp.bom.line.formula.template`
- **Syntax validation** — formulas are checked with `test_python_expr`
  on save; invalid formulas block the wizard with an explicit error

The wizard replaces the raw text field on the BoM line with a small
`fa-code` button that opens the editor, keeping the list view clean.
