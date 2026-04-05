1.  Install the Python dependency (GoRules JDM evaluator):

    ```bash
    pip install zen-engine
    ```

2.  Create a `design.param.definition` for the product family (see
    `design_param_base`).  Link it to the BoM via
    `design_param_definition_id`.

3.  Either load matrix templates via _Load from Template_ on the BoM
    or paste GoRules JDM JSON directly into the four table fields
    (`constraint_table`, `geometry_table`, `material_table`,
    `operation_table`).

4.  On each BoM line, configure:

    - `coeff_default` — 0.0 for O-variants (placeholder lines that
      matrix must activate), 1.0 for always-used components.
    - `matrix_coeff_rule` — key string that must match a row in
      `material_table.content.rules` for runtime coefficient lookup.
    - `quantity_formula` — optional Python formula (see
      `mrp_bom_line_formula_template`).

5.  For semi-finished chains, set `child_definition_id` and
    `param_extraction_map` (JSON mapping parent keys to child keys).
