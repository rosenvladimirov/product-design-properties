# product-design-properties

> Глобалните правила (език, Odoo 18, multi-company) са в ~/.claude/CLAUDE.md.
> Changelog/version правилата са в проектния memory/feedback_changelog_versioning.md.
> Тук са САМО специфичните за тази repo решения и забрани.

---

## Модулна карта

```
design_param_base/              ← Properties дефиниции + design_param_profile
stock_lot_properties/           ← stock.lot Properties полета
mrp_bom_line_formula_template/  ← formula шаблони за bom линии
mrp_bom_line_formula_wizard/    ← formula editor wizard
product_design_assets/          ← ir.attachment активи (GLB/SVG/PNG) на product.product

mrp_design_matrix/              ← ЯДРО
    models/zen_engine.py            GoRules ZEN wrapper (stateless)
    models/mrp_bom.py               matrix таблици + action_load_from_template()
    models/mrp_bom_line.py          coeff, param_extraction_map, child_definition_id
    models/mrp_matrix_template.py   T0/T1/T2/T3 JSON шаблони
    models/mrp_production.py        _generate_design_matrix_moves()
    models/stock_lot.py             _get_design_context(), _create_child_lot()
    static/src/components/          OWL конфигуратор + Three.js 3D превю

mrp_design_matrix_bags/
mrp_design_matrix_corrugated/
mrp_design_matrix_roller_door/
mrp_design_matrix_security_door/
mrp_design_matrix_interior_door/
mrp_design_matrix_smart_display/
mrp_design_matrix_canned_peppers/

sale_design_configurator/       ← SO ред → конфигуратор → лот → МО bridge
```

### Dependency chain (отдолу нагоре)

```
mrp_bom_line_formula_template        собствен formula engine (в това repo)
stock_move_forced_lot_multi          OCA/stock-logistics-workflow — НЕ модифицирай
    └── stock_move_forced_lot_multi_dim   (width/height/thickness на stock.lot)
design_param_base
stock_lot_properties
mrp_bom_line_formula_template
mrp_design_matrix                    зависи от всички горе
    └── mrp_design_matrix_*          индустриални субмодули
sale_design_configurator             зависи от mrp_design_matrix
product_design_assets                зависи само от product + mrp (standalone)
```

---

## Архитектурни решения (чети преди да пишеш код)

**Лотът е носителят на дизайна, не вариантът.**
`stock.lot.design_params` (Properties) описва конкретния production run.
Вариант = продуктова категория. Лот = физическа реализация на поръчката.
Никога не съхранявай дизайн параметри на product variants.

**O-variant логика.**
`coeff_default = 0.0` → MRP го вижда, МО го пропуска.
`coeff_default > 0.0` → матрицата го е активирала, влиза в МО.
O-вариантите са placeholder BOM линии — никога не ги изтривай, никога не им
поставяй qty > 0 ръчно.

**Матричните таблици T0/T1/T2/T3** са JSONB в `mrp.bom` — GoRules JDM формат.
Шаблоните живеят в `mrp.matrix.template` — **шаблоните никога не се редактират директно**.
Ползвай `action_load_from_template()` за копиране в BoM.

**GoRules ZEN Engine** — единствената точка за достъп:
```python
from odoo.addons.mrp_design_matrix.models.zen_engine import ZenWrapper
result = ZenWrapper.evaluate(bom.constraint_table, design_context)
```
Никога не импортирай `zen` директно извън `zen_engine.py`.

**Assets в браузъра (офлайн конфигуратор):**
- IndexedDB → SVG профили, дефиниции, BOM компоненти, DMN правила (структурирани, queryable)
- Cache API (SW) → JPG текстури, GLB модели, PNG thumbnails (URL-based, директно за Three.js)
- localStorage → UI state < 5KB

---

## Workflow — изпълнявай при всяка задача

### Преди да пишеш код

1. Идентифицирай засегнатите модули.
2. Провери dependency chain — никога не добавяй зависимост, която създава цикъл.
3. При промяна в `mrp_design_matrix` ядрото — препрочети архитектурния раздел горе.
4. При несигурност — питай Росен, не импровизирай.

### Забрани (специфични за тази repo)

- **Не пипай** `stock_move_forced_lot_multi` — external OCA. (`mrp_bom_line_formula_quantity` вече НЕ е зависимост — собствено ядро в `mrp_bom_line_formula_template`.)
- **Не пиши** migration scripts — Росен ги прави ръчно.
- **Не променяй** `ir.model.access.csv` записи за модели, които не си добавил в тази сесия.
- **Не добавяй** `depends` в субмодули (`mrp_design_matrix_bags` и др.) извън `mrp_design_matrix` и Odoo base.
- **Не извиквай** `action_load_from_template()` в автоматичен контекст — само user-triggered.
- **Не редактирай** `mrp.matrix.template` записи в код — само UI или demo XML.
- **Не съхранявай** дизайн параметри извън `stock.lot.design_params` и трите реални полета `width/height/thickness`.
- **Не извиквай** `ZenWrapper.evaluate()` извън `_generate_design_matrix_moves()` и SO line валидация.

---

## SO → Лот → МО flow (reference)

```
1. Потребителят избира продукт на SO ред
2. OWL patch: SaleOrderLineProductField.updateProduct()
3. RPC: sale.order.line.get_design_definition_for_product(productId)
4. Ако намери дефиниция → отвори DesignConfiguratorDialog
5. Потребителят задава параметри → real-time T0 валидация
6. Потвърждаване:
   a. stock.lot.generate_design_lot_name(productId)
   b. stock.lot.create({design_params, width, height, thickness})
   c. sale.order.line.set_design_lot([solId], lotId)
7. SO потвърждаване → _prepare_procurement_values() носи design_lot_id
8. МО се създава с lot_producing_id = design_lot_id
9. action_confirm() → _generate_design_matrix_moves()
```

---

## Checklist за нов индустриален субмодул

- [ ] `__manifest__.py` — depends: `["mrp_design_matrix"]`, version `18.0.1.0.0`
- [ ] `data/design_param_definitions.xml` — параметърна схема
- [ ] `data/install_design_params.xml` — `noupdate="1"`, вика `create_design_param_definitions`
- [ ] `data/matrix_templates/*.json` — поне един GoRules JDM файл
- [ ] `data/matrix_templates.xml` — зарежда JSON в `mrp.matrix.template`
- [ ] `demo/demo_bom_*.xml` — поне един BoM с зареден шаблон
- [ ] `CHANGELOG.md` — начален запис
- [ ] Обнови root `CHANGELOG.md`

---

## Конвенции

| Нещо | Конвенция |
|------|-----------|
| Lot name sequence | `stock.lot.serial` или fallback `{parent}-{product_code}` |
| Дизайн контекст ключове | `width`, `height`, `thickness` (lowercase) |
| GoRules error колона | `errors` (list of `{message}`) |
| GoRules warning колона | `warnings` (list of `{message}`) |
| O-variant coeff поле | `coeff_default = 0.0` |
| SVG path id конвенция | kebab-case: `slat-body`, `insulation-fill` |
| Assets mimetype 3D | `model/gltf-binary` |
| IDB database name | `DesignConfiguratorDB` (version 1) |
| Three.js версия | r128 |
| Лиценз | AGPL-3 навсякъде |
| OCA target | OCA/manufacture + OCA/stock-logistics-workflow |
