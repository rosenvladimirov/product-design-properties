---
name: Ролетна щора Teolino Roll — design matrix задание
description: Setup на parametric design matrix за RS-ROLL продукта в dev-teo-accounting; SO configure → lot params → BoM формули
type: project
originSessionId: b0355d11-9d9b-40a2-830b-ecda9fdc15a2
---
## Задание

Имплементиране на design-matrix workflow за продукта **„Ролетна щора Teolino Roll“** в `dev-teo-accounting`: клиентът да конфигурира щора в SO line (размери, вид ламела, задвижване, кутия, водачи), а MO да генерира BoM с реални количества според параметрите.

**Why:** Без матрица всяка комбинация изисква отделен SKU/BoM (експлозия от варианти). Параметричният подход държи 1 product.template + лот със стойности, а BoM редовете се изчисляват с формули. Аналог на mrp_design_matrix_roller_door pattern-а от стека.

**How to apply:** Преди да добавяш атрибути/варианти на този продукт — провери дали не може да стане параметър в `design.param.definition` id=2 (`roller_door`) или в `product.template.design_properties` (template-specific).

## Текущо състояние (2026-05-04)

### Продукт + definition
- `product.template` id=**943** „Ролетна щора Teolino Roll“ (`RS-ROLL`)
  - `type=consu`, `tracking=lot`, `design_param_definition_id=2`
  - `design_properties` (template-specific): Width (mm) default 900, Height (mm) default 2100, Thickness (mm) default 40
- `design.param.definition` id=**2** „Roller Shutter“ (code=`roller_door`, industry=`doors`)
  - 6 параметъра: slat_type, drive_type, box_size, guide_type, has_insulation, has_mosquito_net

### BoM (НЕДОВЪРШЕН)
- `mrp.bom` id=**200**, 6 lines: Ламели PVC/AL, Мотор Somfy, Странични профили, Кутия ролетна, Вал с пружина, Манивела (корда)
- **Всички редове са с константни qty без формули** (`quantity_formula=False`, `formula_template_id=False`, `param_attribute_map=False`)
- Пример test lot 1565 (0000007) от SO S00187 line 409: Width=2000, Height=2000, slat_type=AL_foam, drive_type=manual, box_size=165, guide_type=AL_feather → MO ще консумира пак: 1 ламел, 1 мотор, 2 водача, 1 (обща) кутия, 1 вал, 1 манивела (БЕЗ да отчита параметрите)

### Какво остава да се направи
1. **Формули за qty** на 6 BoM lines:
   - Ламели: `Height / slat_step[slat_type]` (PVC≈9 мм, AL≈8.5 мм)
   - Водачи: 2 (постоянно)
   - Мотор Somfy: `1 if drive_type in ('electric','radio') else 0`
   - Манивела: `1 if drive_type in ('manual','chain') else 0`
2. **`param_attribute_map`** (JSON) за кутия — мап `box_size=137/165/180/205` → различен product_id
3. **`lot_dynamic=True`** на редовете, чието qty зависи от лот
4. Реални коефициенти от потребителя (slat_step, продукти за box_size variants)

## Custom override модул

Локация: `C:\Users\lytopalov\Documents\odoo_addons\sale_design_configurator_summary_fix\` (+ ZIP)
Inсталиран на dev като `sale_design_configurator_summary_fix` v18.0.1.0.0 (id 2920, auto_install=True).

**Какво поправя:**
1. `_compute_design_params_summary` — оригиналният upstream итерира `lot.design_params` като плосък dict и слага UUID hash-ове в summary. Override чете през `lot.read(['design_params'])[0]['design_params']` (rich list-of-dict с merged metadata от template + definition) — резолва selection labels, показва human-readable strings.
2. `_get_sale_order_line_multiline_description_sale` — append-ва summary като bullet list под `name` на SO line; работи в форма + PDF report + invoice.
3. View patch на `design_param_base.design_param_definition_view_form`:
   - `validation_rules` widget=`json` (несъществуващ в v18) → `widget="ace" options='{"mode": "json"}'`
   - `design_params_definition` без widget → `widget="ace" options='{"mode": "json"}'` (workaround)

## Открит upstream bug

`design_param_base/views/design_param_definition_views.xml` използва `widget="json"` (несъществуващ) и `<field name="design_params_definition"/>` без работещ widget. Upstream **няма `static/src/`** — никакъв custom JS widget за редакция на properties_definition. В Odoo 18 Community няма стандартен widget за самостоятелна edit на properties_definition (само вграден inline в `properties` widget при edit на конкретен запис).

**Why:** Затова таб „Parameter Definitions“ в design.param.definition form-ата излиза празен. Не е markdown_viewer_locale Owl bug (макар че е и той инсталиран в dev v18.0.3.0.7).

**How to apply:** Дългосрочен fix — да се напише custom Owl widget `properties_schema_editor` (~150 LOC JS + template) и PR към rosenvladimirov/product-design-properties. Като workaround сега — JSON ace редактор или редакция през stock.lot's properties widget (който работи нормално).

## Confiгурация през SO — къде се вижда

`sale.order.line` полета (от `sale_design_configurator`):
- `design_lot_id` → m2o към `stock.lot` (тук са реалните стойности)
- `design_param_definition_id` → кой набор се ползва
- `design_params_summary` → char (вече четим след fix-а)
- `has_design_definition` → bool

Реалните стойности живеят на `stock.lot.design_params` (properties field).

## Меню

- Manufacturing → Configuration → **Design Parameter Definitions** (action 1642, xml_id `design_param_base.design_param_definition_action`)
- Manufacturing → Configuration → **Matrix Templates** (action 1644)

## Свързани модули (всички installed на dev)

design_param_base 18.0.1.0.3, mrp_design_matrix 18.0.1.7.1, mrp_design_matrix_roller_door 18.0.1.3.0, sale_design_configurator 18.0.1.5.0, stock_lot_properties 18.0.1.0.0, mrp_bom_line_formula_template 18.0.1.3.0, mrp_bom_line_formula_wizard 18.0.1.1.0, product_design_assets 18.0.1.1.0
