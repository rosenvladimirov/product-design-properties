1.  Open the formula editor wizard (see
    `mrp_bom_line_formula_wizard`).
2.  Click the _Ask Claude_ button next to the formula field.
3.  The Claude terminal opens in a modal dialog.  Claude automatically
    reads the wizard record to understand the BoM line context.
4.  Describe what you want the formula to compute in plain language
    (Bulgarian or English).  Claude will propose a formula using the
    available design parameters and ask for confirmation.
5.  Once you confirm, Claude writes the formula back to the wizard and
    calls `odoo_refresh`; the dialog closes itself and the wizard
    editor shows the generated formula, ready for _Apply_.
