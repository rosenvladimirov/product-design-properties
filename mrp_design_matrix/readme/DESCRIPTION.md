Ядро на design-driven производството. Превръща параметричен BoM в
конкретна производствена поръчка (MO) чрез оценка на четири GoRules DMN
таблици (T0/T1/T2/T3) спрямо плосък design контекст, събран от
производствения lot:

- **T0 — Constraints** (`constraint_table`) — блокира или предупреждава
  при невалидни комбинации от параметри (напр. „height < 1900 mm“ →
  `level=error`).
- **T1 — Geometry** (`geometry_table`) — изчислява производни размери и
  forced стойности (напр. `door_weight_kg_m2`, `min_thickness_mm`),
  които стават налични за T2/T3 и BoM line формулите.
- **T2 — Materials** (`material_table`) — съставът на ведомостта.
  Поддържа три типа редове:

  1.  _Coefficient_ — настройва количеството на стандартна BoM линия
      през lookup по `matrix_coeff_rule`.
  2.  _Direct ref_ — добавя ad-hoc move за външно референциран продукт.
  3.  _PTAV_ — резолва вариант на продукт, мачвайки стойностите на
      design параметрите спрямо `product.template.attribute.value.name`.

- **T3 — Operations** (`operation_table`) — условни workorder-и, които
  се добавят само когато правилото им за активиране съвпадне.

Engine-ът е stateless — чете матрицата JSON от BoM-а и design контекста
от lot-а, после генерира raw moves и workorder-и върху MO-то. Без
caching, без странични ефекти извън създаване на `stock.move` и
`mrp.workorder`.

Допълнителни функционалности:

- **`DesignMatrixField`** — OWL widget, който заменя ACE JSON редактора
  с визуална DMN таблица (read-only + edit режим, JSON↔Table
  превключване, hitPolicy селектор, drag-reorder).
- **Matrix Preview** — smart бутон на BoM формата, който отваря диалог
  с контроли за параметрите и live T0/T1/T2/T3 оценка за бърза итерация
  без създаване на реални MO-та.
- **Semi-finished chain** — `child_definition_id` + `mto_stop` позволяват
  BoM линията или да породи child lot (ново MO), или да търси
  съществуващи stock lots по design параметри (MTO stop).
