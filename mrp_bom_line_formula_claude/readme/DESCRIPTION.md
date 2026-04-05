AI-assisted formula generation for BoM line quantity formulas.  Adds an
_Ask Claude_ button to the formula editor wizard that opens the Claude
Code terminal in an embedded iframe, following the concept of
`l10n_bg_claude_terminal` (MCP server + live refresh).

Architecture:

- The wizard exposes a `claude_brief` JSON field with the full context
  Claude needs (BoM line, product, UoM, design parameter definition,
  matrix tables present on the BoM) plus a `claude_instructions` field
  with the task description.
- Clicking _Ask Claude_ opens the terminal iframe with URL parameters
  (`ODOO_MODEL=mrp.bom.line.formula.wizard`, `ODOO_RES_ID=<wizard_id>`,
  `FORMULA_TASK=generate_bom_formula`).
- Claude reads the wizard via `odoo_read`, generates the formula, and
  writes it back via `odoo_write` + `odoo_refresh`.
- The wizard's bus listener reloads on `CLAUDE_REFRESH` events so the
  generated formula appears in the editor without user action.
