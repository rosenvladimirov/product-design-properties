# MRP Design Matrix — System Requirements Document (SRD)

**Version:** 1.0 | **Date:** March 2026 | **Author:** Rosen Vladimirov \<vladimirov.rosen@gmail.com\> | BL Consulting | Odoo Silver Partner

---

## 1. Architecture Overview

The system is implemented as a stack of Odoo modules with a clear dependency hierarchy. The core is generic — industry-specific logic lives in separate submodules.

| Module | Type | Description |
|---|---|---|
| `mrp_bom_line_formula_template` | Own | Formula-based quantity on BoM line (own evaluation core; replaced former OCA dependency). |
| `stock_move_forced_lot_multi` | Own (PR candidate) | Forced lot assignment on raw material moves. Propagation to PO. |
| `stock_move_forced_lot_multi_dim` | Submodule | `width/height/thickness` on `stock.lot`. |
| `mrp_bom_formula_lot_dimension` | **NEW — bridge** | Injects lot dims + Properties into the formula context. ~50 lines. |
| `mrp_design_matrix` | **NEW — core** | Main module: definitions, templates, matrices, MO generation. |
| `mrp_design_matrix_bags` | Submodule | Garbage bags. |
| `mrp_design_matrix_corrugated` | Submodule | Boxes + corrugated board. |
| `mrp_design_matrix_roller_door` | Submodule | Roller doors. |
| `mrp_design_matrix_security_door` | Submodule | Security doors (RC logic). |
| `mrp_design_matrix_interior_door` | Submodule | Interior doors. |

---

## 2. Data Models

### 2.1 `mrp.design.param.definition`

Groups parameter definitions. Analogous to `component.definition.properties` from `product_electrical_properties`.

| Field | Description |
|---|---|
| `code` | Unique code: `'bags'`, `'roller_door'` |
| `name` | Human-readable name |
| `industry` | Grouping: `'bags'`, `'doors'`, `'corrugated'` |
| `parent_id` | `Many2one → self` (inheritance) |
| `design_params_definition` | `PropertiesDefinition` — the parameter schema |

Definitions are loaded from custom XML on installation via `create_design_param_definitions()`. The format follows the pattern of `component_definition.xml`.

### 2.2 `mrp.matrix.template`

Templates with rules. The client never edits the template directly.

| Field | Description |
|---|---|
| `name` | Name: `'Bags - standard with print'` |
| `industry` | For filtering |
| `constraint_table` | `Json` (JSONB) — T0 rules in GoRules format |
| `geometry_table` | `Json` — T1 rules |
| `material_table` | `Json` — T2 rules |
| `operation_table` | `Json` — T3 rules |

### 2.3 `mrp.bom` (extended)

| Field | Description |
|---|---|
| `design_param_definition_id` | `Many2one → mrp.design.param.definition` |
| `matrix_template_id` | `Many2one → mrp.matrix.template` (reference only) |
| `constraint_table` | `Json` — T0 copy, editable |
| `geometry_table` | `Json` — T1 copy |
| `material_table` | `Json` — T2 copy |
| `operation_table` | `Json` — T3 copy |

### 2.4 `mrp.bom.line` (extended)

| Field | Description |
|---|---|
| `quantity_formula` | `Text` — formula (from OCA module, existing) |
| `matrix_coeff_rule` | `Char` — reference to T2 row for coefficient |
| `coeff_default` | `Float` — `0.0` for O-variants, `1.0` for real ones |
| `product_tmpl_id` | `Many2one → product.template` (for PTAV resolution) |
| `param_attribute_map` | `Json` — `{design_key: attr_external_id}` |
| `param_extraction_map` | `Json` — `{child_key: source_or_formula}` |
| `child_definition_id` | `Many2one → mrp.design.param.definition` |
| `mto_stop` | `Boolean` — stops the MTO chain at this level |

### 2.5 `stock.lot` (extended)

| Field | Description |
|---|---|
| `width / height / thickness` | `Float` — real fields (from `_dim` module) |
| `design_param_definition_id` | `Many2one → mrp.design.param.definition` |
| `design_params` | `Properties` — all industry parameters |
| `bom_id` | `Many2one → mrp.bom` (for Properties context) |

---

## 3. Design Parameters — Properties Engine

Follows the pattern of `product_electrical_properties`. Parameters are typed, defined via XML, stored as JSONB, with auto-generated UI.

**Supported types:** `char`, `float`, `boolean`, `selection`.

**Inheritance:** via `parent_id` — the base definition contains common parameters, the extended one adds the specific ones.

| Definition | Parameters |
|---|---|
| Bags | `bag_type, has_tie, has_print, density, resin_type, color` |
| Boxes | `board_type, has_print, die_cut` |
| Corrugated | `grammage, flute_type, board_grade` |
| Roller door | `slat_type, drive_type, has_insulation, has_perforation` |
| Security door | `RC_class, sheet_thickness, lock_type, has_glass, has_electronic_lock` |
| Interior door | `construction, opening, leaf_type, finish, has_glass_panel, has_soundproof, wall_width` |

### XML Format for Definitions

```xml
<records>
    <properties code="bags" name="Bags - Standard">
        <items name="bag_type">
            <item name="type">selection</item>
            <item name="selection">[["sleeve","Sleeve"],["sheet","Sheet"]]</item>
            <item name="default">sleeve</item>
        </items>
        <items name="has_tie">
            <item name="type">boolean</item>
            <item name="default">false</item>
        </items>
    </properties>
</records>
```

### Reading in Python

```python
design_context = {
    "width":     lot.width,
    "height":    lot.height,
    "thickness": lot.thickness,
    "qty":       production.product_qty,
    **{k: v for k, v in (lot.design_params or {}).items()},
}
# → {"width": 600, "bag_type": "sleeve", "has_tie": True, ...}
```

---

## 4. Matrix — GoRules ZEN Engine

**Library:** `zen-engine` (`pip install zen-engine`). Rust + Python bindings. <1ms latency. Embeddable — no external calls.

Matrices are stored as JSONB in `mrp.bom`. They are edited via the `ace_editor` widget in the Odoo UI.

### T0 — Constraints

- Hit policy: `Collect`
- Executed BEFORE everything
- `ERROR` → `UserError`, MO is not created
- `WARNING` → `message_post`, continues

```
ERROR:   perforation + has_insulation    (roller shutter)
         glass + RC_class >= RC4         (security door)
         sheet + slitting operation      (bag)

WARNING: width > 4000 + manual           (roller shutter)
         solid + width > 900             (interior door)
```

### T1 — Geometry

- Hit policy: `Unique`
- Three effect types:
  - `context_modify` — computes an intermediate var (`effective_length`)
  - `context_force` — override with minimum (`sheet_thickness = max(user, RC_min[RC_class])`)
  - `context_derive` — from physics (`motor_class = f(area × slat_weight_per_m2)`)
- Output enriches `full_context` for T2, T3, and the formula module

### T2 — Materials

- Hit policy: `Collect (sum)`
- **Type 1 — O-variant activation:** `{"bom_line_coeff_key": "...", "coefficient": 1.15}`
- **Type 2 — Direct ref:** `{"product_ref": "module.product_xmlid", "quantity": "...", ...}`
- **Type 3 — PTAV resolution:** `{"product_tmpl_ref": "...", "param_attribute_map": {"color": "module.attr_color"}, ...}`

### T3 — Operations

- Hit policy: `Any`
- Conditionally adds workorders
- Output: `{"workcenter_ref": "...", "duration_formula": "...", "sequence": int}`

---

## 5. PTAV Resolution

Design parameter → `product.attribute` → `product.attribute.value` → `product.product` variant.

```
design_params.color = "FF0000"
    ↓ param_attribute_map: {"color": "module.attr_color"}
attribute: Color / value: "FF0000"
    ↓ _get_variant_for_combination(ptav)
product.product: Ink + Color/FF0000
```

**Requirement:** `design_params` values must match `product.attribute.value.name` exactly.

```python
def _resolve_variant_by_ptav(self, tmpl, param_attr_map, design_ctx):
    needed_ptav = self.env["product.template.attribute.value"]
    for param_key, attr_ref in param_attr_map.items():
        value = design_ctx.get(param_key)
        if value is None:
            continue
        attribute = self.env.ref(attr_ref)
        ptav = self.env["product.template.attribute.value"].search([
            ("product_tmpl_id", "=", tmpl.id),
            ("attribute_id",    "=", attribute.id),
            ("name",            "=", str(value)),
        ], limit=1)
        if ptav:
            needed_ptav |= ptav
    return tmpl._get_variant_for_combination(needed_ptav)
```

---

## 6. Semi-Finished Products — Recursive Chain

```
End product lot_1: {bag_type, has_tie, width, color, thickness}
    MO Level 1
        ├── Film (semi-finished)
        │       lot_2: {bag_type, width, color, thickness}
        │       ← param_extraction_map from BoM line
        │       MO Level 2 → resin (mto_stop=True → PO)
        │
        └── Tie band
                lot_3: {tie_length: height+50}
                ← transformation via safe_eval
                mto_stop=True → PO or stock
```

### param_extraction_map Format

```json
{
  "bag_type":   "bag_type",
  "width":      "width",
  "tie_length": "height + 50"
}
```

Simple key → direct copy. Expression → `safe_eval` against the parent lot context.

### MTO Stop Logic

| `mto_stop` | Action |
|---|---|
| `False` | Creates a new MO + `_create_child_lot()` |
| `True` | `_find_matching_lot()` from stock → if not found → PO with parameters |

---

## 7. MO Construction — Algorithm

```python
def _generate_design_matrix_moves(self):
    bom = self.bom_id
    if not bom.constraint_table:
        return  # standard BoM

    lot = self.lot_producing_id
    ctx = {
        "width": lot.width, "height": lot.height,
        "thickness": lot.thickness, "qty": self.product_qty,
        **{k: v for k, v in (lot.design_params or {}).items()},
    }

    # T0 — constraints
    t0 = engine.create_decision(bom.constraint_table).evaluate(ctx)
    for e in t0.get("errors", []):
        raise UserError(_("Design constraint: %s") % e["message"])
    for w in t0.get("warnings", []):
        self.message_post(body=_("Warning: %s") % w["message"])

    # T1 — geometry (forced values override user input)
    t1 = engine.create_decision(bom.geometry_table).evaluate(ctx)
    full_ctx = {**ctx, **t1}

    # T2 — BoM lines × (formula × coeff) [Type 1: O-variants]
    for line in bom.bom_line_ids:
        qty_base = line._eval_quantity_formula(..., context=full_ctx)
        coeff = self._eval_matrix_coeff(line, full_ctx)
        if qty_base * coeff > 0.0:
            self._create_matrix_move_raw(line.product_id, qty_base * coeff, ...)

    # T2 — ad-hoc [Type 2: direct / Type 3: PTAV]
    for item in engine.create_decision(bom.material_table).evaluate(full_ctx).get("result", []):
        if item.get("coefficient", 0.0) > 0.0:
            product = self._resolve_t2_product(item, full_ctx)
            self._create_matrix_move_raw(product, ...)

    # T3 — operations
    for op in engine.create_decision(bom.operation_table).evaluate(full_ctx).get("result", []):
        self._create_matrix_workorder(self.env.ref(op["workcenter_ref"]), op)

    # Semi-finished: child lots + mto_stop
    for move in self.move_raw_ids.filtered(lambda m: m.bom_line_id.child_definition_id):
        line = move.bom_line_id
        if line.mto_stop:
            match = self._find_matching_lot(move.product_id, ...)
            if match:
                move.forced_lot_ids = [(4, match.id)]
        else:
            child_lot = self._create_child_lot(lot, line)
            move.forced_lot_ids = [(4, child_lot.id)]
```

---

## 8. Repository Structure

```
mrp_design_matrix/
    models/
        mrp_design_param_definition.py
        mrp_matrix_template.py
        mrp_bom.py
        mrp_bom_line.py
        mrp_production.py
        stock_lot.py
    views/
        mrp_bom_views.xml           ← "Design Matrix" tab + ace_editor
        mrp_matrix_template_views.xml
        mrp_design_param_definition_views.xml
    data/
        base_param_definitions.xml

mrp_design_matrix_{industry}/
    data/
        design_param_definitions.xml
        install_design_params.xml
        matrix_templates/
            {name}.json
    demo/
        demo_bom_{industry}.xml
```

---

## 9. OCA Requirements

- License: AGPL-3
- Dependencies only from OCA/Odoo CE
- `zen-engine` in `external_dependencies`
- Tests: at least one per feature
- Pre-commit: `ruff`, `black`, OCA checks
- Towncrier changelog
- `README.rst` with DESCRIPTION, USAGE, CONFIGURE
