# Design Matrix UI Concept

> Графичен преглед на GoRules DMN правилата — две компоненти:
> 1. **DesignMatrixField** — визуална таблица в BoM формата (заменя ACE JSON editor)
> 2. **RuleMatrixPreview** — real-time правилна индикация в конфигуратора (заменя 3D viewport когато няма GLB/SVG)

---

## 1. BoM форма — `DesignMatrixField` widget

### Какво заменя

ACE JSON editor за `constraint_table`, `geometry_table`, `material_table`, `operation_table`

### Визуален формат — DMN Decision Table grid

```
+------------------------------------------------------------------+
| T0 -- Constraints                         hitPolicy: COLLECT   v |
+----------+----------+---------+---------+----------+-------------+
| INPUTS                                  | OUTPUTS               |
+----------+----------+---------+---------+----------+-------------+
| width    | height   | constr. |leaf_type| level    | message     |
+----------+----------+---------+---------+----------+-------------+
| < 600    |          |         |         | *error   | Min. 600    |
| > 2400   |          |         |         | *error   | Max. 2400   |
|          | < 1900   |         |         | *error   | Min. 1900   |
|          |          | "glass" |         | *error   | Glass+...   |
| < 1200   |          |         |"double" | *error   | Double leaf |
| > 1100   |          | "solid" |         | !warn    | Heavy       |
+----------+----------+---------+---------+----------+-------------+
         [JSON]  [+ Row]  [+ Input]  [+ Output]
```

### Файлова структура

```
mrp_design_matrix/static/src/components/design_matrix_field/
  design_matrix_field.js       -- OWL field widget
  design_matrix_field.xml      -- Table template
  design_matrix_field.scss     -- DMN table styling
```

### Регистрация

```javascript
// design_matrix_field.js
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DesignMatrixField extends Component {
    static template = "mrp_design_matrix.DesignMatrixField";
    static props = {
        ...standardFieldProps,
        tableType: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            viewMode: "table",   // "table" | "json"
            collapsed: false,
        });
    }

    get table() {
        return this.props.record.data[this.props.name] || null;
    }

    get inputs()  { return this.table?.content?.inputs  || []; }
    get outputs() { return this.table?.content?.outputs || []; }
    get rules()   { return this.table?.content?.rules   || []; }
    get hitPolicy() { return this.table?.content?.hitPolicy || "collect"; }
}

export const designMatrixField = {
    component: DesignMatrixField,
    displayName: "Design Matrix",
    supportedTypes: ["json"],
    extractProps: ({ options }) => ({
        tableType: options.table_type,
    }),
};

registry.category("fields").add("design_matrix", designMatrixField);
```

### XML промяна в mrp_bom_views.xml

```xml
<field name="constraint_table"
       widget="design_matrix"
       options="{'table_type': 't0'}"
       nolabel="1"/>
```

### Компонентна структура

```
DesignMatrixField
  State: { table (parsed JSON), viewMode, collapsed }
  Props: record, name, readonly, tableType

  Header bar
    Table name (table.name)
    hitPolicy badge (collect/first/priority)
    Collapse toggle
    Mode toggle: [Table] [JSON]

  Column headers
    Input columns (сини) -- table.content.inputs[]
      + бутон за нова input колона (edit mode)
    Output columns (зелени) -- table.content.outputs[]
      + бутон за нова output колона (edit mode)

  Rule rows -- table.content.rules[]
    Всяка клетка: <input> в edit, <span> в read
    Празна клетка = "--" (wildcard, всяка стойност минава)
    Output level клетка:
      "error"   -> червен badge
      "warning" -> жълт badge
      стойност  -> неутрален
    Row hover: highlight + delete бутон
    Row drag handle за пренареждане

  Footer toolbar (edit mode only)
    [+ Add Rule]
    [+ Add Input]
    [+ Add Output]

  JSON fallback mode
    Вграден CodeEditor (Odoo ACE) за raw edit
```

### Стилизация

| Елемент | Стил |
|---------|------|
| Input header | `background: #e8f4fd`, `border-bottom: 2px solid #2196F3` |
| Output header | `background: #e8f5e9`, `border-bottom: 2px solid #4CAF50` |
| Error badge | `background: #f8d7da`, `color: #721c24` |
| Warning badge | `background: #fff3cd`, `color: #856404` |
| Празна клетка | `color: #ccc`, показва "--" |
| hitPolicy badge | `border-radius: 4px`, `font-size: 10px`, uppercase |
| Row hover | `background: #f5f5f5` |
| Edit cell | `border: 1px dashed #aaa` при focus |

### Data flow

**Read:**
```
record.data[fieldName] -> parse JSON
  -> extract inputs[], outputs[], rules[]
  -> render <table> grid
```

**Edit:**
```
User edits cell -> updateRule(rowIdx, colId, value)
  -> rebuild table JSON object
  -> this.props.record.update({ [fieldName]: newTableJSON })
  -> Odoo ORM dirty flag -> Save triggers write to DB
```

---

## 2. Конфигуратор — `RuleMatrixPreview`

### Какво заменя

Десния панел (`.o_cfg_viewport`) с Three.js canvas — **само когато продуктът няма 3D assets (GLB) и няма SVG профили**. Ако има GLB/SVG, запазва съществуващия 3D viewport.

### Layout

```
+---------------------------------------------------------------------+
| Configurator Dialog (770px wide)                                     |
+----------+----------------------------------------------------------+
| LEFT     | RIGHT: Rule Matrix Preview                               |
| PANEL    |                                                           |
| (260px)  | +-- T0 Constraints ------------------------------------+ |
|          | | v Width 900mm -- OK                                   | |
| Width    | | v Height 2100mm -- OK                                 | |
| [====]   | | x Glass construction does not support soundproofing   | |
| 900 mm   | | ! Solid wood > 1100mm -- heavy door                   | |
|          | +------------------------------------------------------+ |
| Height   |                                                           |
| [====]   | +-- T1 Geometry ---------------------------------------+ |
| 2100 mm  | | door_weight_kg_m2 = 12                                | |
|          | | min_thickness_mm  = 35                                | |
| Constr.  | | leaf_count        = 1                                 | |
| [HDF]    | +------------------------------------------------------+ |
|          |                                                           |
| Opening  | +-- T2 Materials --------------------------------------+ |
| [Left]   | |                                                       | |
|          | | Kasa             1 x 1.0 = 1.0                        | |
| Leaf     | | Lock             1 x 1.0 = 1.0                        | |
| [Single] | | Leaf             1 x 1.0 = 1.0  <- leaf-qty           | |
|          | | Hinges           3 x 1.0 = 3.0  <- hinge-qty          | |
| Finish   | | Handle           1 x 1.0 = 1.0                        | |
| [Veneer] | |                                                       | |
|          | | <- double: Leaf x2.0, Hinges x2.0                     | |
| [ ] Glass| +------------------------------------------------------+ |
| [ ] Sound|                                                           |
|          | +-- T3 Operations -------------------------------------+ |
| Wall     | | (no active operations)                                | |
| [100] mm | |                                                       | |
|          | | <- Glass Panel: Glass fitting (30min)                 | |
| -------- | | <- Soundproof: Insulation fitting (20min)             | |
| Errors   | | <- Lacquer: Lacquering (60min)                        | |
| x ...    | +------------------------------------------------------+ |
| -------- |                                                           |
| [Create] |                                                           |
| [Cancel] |                                                           |
+----------+----------------------------------------------------------+
```

### Файлова структура

```
sale_design_configurator/static/src/components/design_configurator/
  design_configurator.js          -- модифициран: условен viewport
  design_configurator.xml         -- добавен rule_matrix_preview блок
  design_configurator.scss        -- нови стилове за preview
  rule_matrix_preview.js          -- НОВ: дъщерен OWL component
  rule_matrix_preview.xml         -- НОВ: template
```

### Решение кога да се показва

```javascript
// В design_configurator.js
get showRulePreview() {
    const has3D = this.props.mainProductAssets?.models_3d?.length > 0;
    const hasSVG = this.props.profiles?.length > 0
                   && this.props.profiles[0]?.svg_content;
    const hasMatrix = this._hasMatrixTables();
    return !has3D && !hasSVG && hasMatrix;
}
```

### Template (условен viewport)

```xml
<!-- В design_configurator.xml -->
<div class="o_cfg_viewport" t-if="!showRulePreview">
    <!-- Съществуващ Three.js canvas -->
    <canvas t-ref="canvas"/>
    ...
</div>
<div class="o_cfg_rule_preview" t-if="showRulePreview">
    <RuleMatrixPreview
        params="params"
        bomId="bomId"
        bomLines="bomLines"
        constraintTable="constraintTable"
        geometryTable="geometryTable"
        materialTable="materialTable"
        operationTable="operationTable"
    />
</div>
```

### RuleMatrixPreview компонент

```javascript
class RuleMatrixPreview extends Component {
    static template = "sale_design_configurator.RuleMatrixPreview";
    static props = {
        params: Object,              // reactive -- промяна рендерира отново
        bomId: Number,
        bomLines: { type: Array },   // BoM линии с product_name, qty, coeff_rule
        constraintTable: Object,     // GoRules JDM
        geometryTable: Object,
        materialTable: Object,
        operationTable: Object,
    };
}
```

### Секции

#### T0 -- Constraints (real-time)

```
Алгоритъм за всеки rule в constraintTable.content.rules:
  1. Провери всеки input спрямо текущите params
  2. Ако rule match-ва:
     - level == "error"   -> червен ред с x икона
     - level == "warning" -> жълт ред с ! икона
  3. Ако НЕ match-ва -> зелен ред с v "OK"
  4. Inputs с празна стойност ("") -> wildcard, винаги match
```

Визуално: вертикален списък, анимиран при промяна (fade in/out)

#### Клиентска евалюация (без ZenWrapper/сървър)

```javascript
_evaluateRule(rule, params, inputs) {
    for (const input of inputs) {
        const ruleVal = rule[input.id];
        if (!ruleVal) continue;  // empty = wildcard
        const paramVal = params[input.id];

        if (ruleVal.startsWith('"'))    return paramVal === JSON.parse(ruleVal);
        if (ruleVal.startsWith('> '))   return paramVal > parseFloat(ruleVal.slice(2));
        if (ruleVal.startsWith('< '))   return paramVal < parseFloat(ruleVal.slice(2));
        if (ruleVal.startsWith('>= '))  return paramVal >= parseFloat(ruleVal.slice(3));
        if (ruleVal.startsWith('<= '))  return paramVal <= parseFloat(ruleVal.slice(3));
        if (ruleVal.startsWith('!= '))  return paramVal !== JSON.parse(ruleVal.slice(3));
        if (ruleVal === 'true')         return paramVal === true;
        if (ruleVal === 'false')        return paramVal === false;
    }
    return true;  // all conditions passed
}
```

#### T1 -- Geometry (computed values)

```
Алгоритъм:
  1. Оценявай rules по hitPolicy
  2. hitPolicy="first" -> покажи само първия match
  3. hitPolicy="collect" -> покажи всички matches
  4. Показвай computed стойности като key = value list

Визуално: компактна таблица с 2 колони (variable | value)
  - Highlight-ни changed стойностите с анимация при param промяна
```

#### T2 -- Materials (BoM composition)

```
Алгоритъм:
  1. За всяка BoM линия:
     a. base_qty = line.product_qty
     b. Ако line.matrix_coeff_rule:
        - Търси match в materialTable.content.rules
          където bom_line_coeff_key == line.matrix_coeff_rule
        - coeff = matched coefficient ИЛИ line.coeff_default
     c. Иначе coeff = line.coeff_default
     d. final_qty = base_qty x coeff
  2. Покажи всички линии с qty x coeff = final
  3. Линии с final_qty == 0 -> сиви, зачеркнати (O-variant inactive)
  4. Линии с coeff != 1.0 -> highlight (матрицата промени нещо)

Визуално: таблица с колони [Компонент | Qty | x Coeff | = Final]
  - Активните са зелени
  - Inactive O-variants са сиви
  - Промените от матрицата са маркирани
```

#### T3 -- Operations (workorders)

```
Алгоритъм:
  1. Оценявай всяко T3 правило спрямо текущите params
  2. Matched правила -> покажи workorder карта
  3. Неmatched -> покажи скрити (collapsed), сиви

Визуално: хоризонтални карти за всяка операция
  [Lacquering | 60 min | Workcenter: Painting]
  - Активни: зелена лява лента
  - Неактивни: сива, dashed border
```

### Данни за зареждане (в DesignConfiguratorDialog)

```javascript
// Нови RPC calls в _loadDefinition():
// 1. Зареди BoM таблиците
const bom = await this.orm.read("mrp.bom", [bomId], [
    "constraint_table", "geometry_table",
    "material_table", "operation_table"
]);

// 2. Зареди BoM линиите с matrix полетата
const lines = await this.orm.searchRead("mrp.bom.line",
    [["bom_id", "=", bomId]],
    ["product_id", "product_qty", "coeff_default", "matrix_coeff_rule"]
);
```

### Стилизация

```scss
.o_cfg_rule_preview {
    background: #fafafa;
    height: 100%;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.o_cfg_rule_section {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
}

.o_cfg_rule_section_header {
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;

    &.t0 { background: #fce4ec; color: #c62828; border-left: 3px solid #e53935; }
    &.t1 { background: #e3f2fd; color: #1565c0; border-left: 3px solid #1e88e5; }
    &.t2 { background: #e8f5e9; color: #2e7d32; border-left: 3px solid #43a047; }
    &.t3 { background: #fff3e0; color: #e65100; border-left: 3px solid #fb8c00; }
}

// Constraint rows
.o_cfg_rule_row {
    padding: 4px 12px;
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background 0.2s, opacity 0.3s;

    &.matched   { background: rgba(244, 67, 54, 0.06); }
    &.ok        { color: #81c784; }
    &.error     { color: #e53935; font-weight: 500; }
    &.warning   { color: #f9a825; }
}

// Material lines
.o_cfg_mat_line {
    &.inactive  { opacity: 0.4; text-decoration: line-through; }
    &.modified  { background: rgba(255, 235, 59, 0.1); }
}

// Operation cards
.o_cfg_op_card {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid #e0e0e0;

    &.active    { border-left: 3px solid #43a047; background: #f1f8e9; }
    &.inactive  { border: 1px dashed #ccc; opacity: 0.5; }
}
```

---

## Зависимости между компонентите

```
DesignConfiguratorDialog
  _loadDefinition()
    existing RPC calls (definition, profiles, assets...)
    NEW: load BoM matrix tables + BoM lines
         |
         v
  DesignConfiguratorWidget
    showRulePreview getter
      true  -> RuleMatrixPreview (reactive to params)
      false -> Three.js canvas (existing)

    params (useState proxy)
      onChange
         v
    RuleMatrixPreview
      _evaluateT0(params) -> constraint results
      _evaluateT1(params) -> geometry values
      _evaluateT2(params, bomLines) -> material composition
      _evaluateT3(params) -> operation list
```

---

## Поетапен план за имплементация

| Фаза | Компонент | Обхват | Модул |
|------|-----------|--------|-------|
| Ф1 | `DesignMatrixField` | Read-only table renderer | `mrp_design_matrix` |
| Ф2 | `DesignMatrixField` | Edit mode (inline cells, add/remove rows/cols) | `mrp_design_matrix` |
| Ф3 | `DesignMatrixField` | JSON<->Table toggle, hitPolicy selector, drag reorder | `mrp_design_matrix` |
| Ф4 | `RuleMatrixPreview` | T0 real-time constraint evaluation | `sale_design_configurator` |
| Ф5 | `RuleMatrixPreview` | T1 + T2 + T3 sections, full BoM composition | `sale_design_configurator` |
| Ф6 | Integration | Auto-detect 3D/SVG/Matrix fallback, BoM data loading | `sale_design_configurator` |

---

## Технически бележки

### Odoo 18 field widget регистрация

```javascript
registry.category("fields").add("design_matrix", {
    component: DesignMatrixField,
    displayName: "Design Matrix",
    supportedTypes: ["json"],
    supportedOptions: [
        { label: "Table Type", name: "table_type", type: "string" },
    ],
    extractProps: ({ options }) => ({
        tableType: options.table_type,
    }),
});
```

### GoRules JDM формат (reference)

```json
{
    "id": "t0-roller",
    "name": "T0 Constraints",
    "type": "decisionTable",
    "content": {
        "hitPolicy": "collect",
        "inputs":  [{"id": "width", "name": "width"}, ...],
        "outputs": [{"id": "level", "name": "level"}, ...],
        "rules":   [{"width": "> 3300", "level": "\"error\"", ...}, ...]
    }
}
```

### Правила за евалюация на клетки

| Формат | Значение | Пример |
|--------|----------|--------|
| `""` (празно) | Wildcard -- всяка стойност минава | |
| `"\"value\""` | Exact string match | `"\"PVC\""` |
| `"> N"` | По-голямо от N | `"> 3000"` |
| `"< N"` | По-малко от N | `"< 500"` |
| `">= N"` | По-голямо или равно | `">= 1200"` |
| `"<= N"` | По-малко или равно | `"<= 2400"` |
| `"!= \"val\""` | Не е равно на | `"!= \"none\""` |
| `"true"` / `"false"` | Boolean match | `"true"` |
| `"N"` (число) | Числена стойност (за outputs) | `"3.5"` |
