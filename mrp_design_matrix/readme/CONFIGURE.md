1.  Инсталирайте Python зависимостта (GoRules JDM evaluator):

    ```bash
    pip install zen-engine
    ```

2.  Създайте `design.param.definition` за продуктовото семейство (виж
    `design_param_base`). Свържете я към BoM-а през полето
    `design_param_definition_id`.

3.  Заредете матрични шаблони през _Load from Template_ на BoM-а, или
    поставете GoRules JDM JSON директно в четирите table полета
    (`constraint_table`, `geometry_table`, `material_table`,
    `operation_table`).

4.  За всяка BoM линия конфигурирайте:

    - `coeff_default` — 0.0 за O-варианти (placeholder редове, които
      матрицата трябва да активира), 1.0 за постоянно използвани
      компоненти.
    - `matrix_coeff_rule` — ключов стринг, който трябва да съвпадне с
      ред в `material_table.content.rules` за runtime lookup на
      коефициента.
    - `quantity_formula` — опционална Python формула (виж
      `mrp_bom_line_formula_template`).

5.  За semi-finished вериги задайте `child_definition_id` и
    `param_extraction_map` (JSON, който мапва родителски ключове към
    child ключове).
