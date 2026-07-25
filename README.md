# MRP Design Matrix

**Design-driven manufacturing for Odoo 18 with lot-level parameters.**

[![License: AGPL-3](https://img.shields.io/badge/licence-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Odoo 18](https://img.shields.io/badge/Odoo-18-blueviolet.svg)](https://www.odoo.com)

---

## The Problem

Manufacturing companies working on make-to-order basis face a fundamental limitation in Odoo: the standard system manages products as categories, but cannot describe the **specific physical item** that needs to be produced right now, for this particular customer, with these exact parameters.

The result: engineering departments maintain thousands of product variants (one per parameter combination), or rely on paper-based specifications outside the system. In both cases, planning, traceability, and costing are incomplete.

## The Solution

**MRP Design Matrix** introduces a new conceptual layer: the **production lot carries the design specification** of the item. The BoM is parametric -- materials and quantities are computed automatically from the lot's parameters. A rule system (matrix) governs the transformation.

### Key Concepts

| Concept | Description |
|---|---|
| **Lot = Design carrier** | `stock.lot` with Properties describes the specific production run. Variant = category. Lot = physical realization. |
| **BoM = Planning view** | Contains all possible materials, including O-variants (conditional items with `coeff=0.0`). |
| **MO = Execution view** | Only active materials appear. O-variants are activated by the matrix (`coeff > 0.0`). |
| **Design Matrix (T0-T3)** | Four rule tables transform design parameters into concrete materials and operations. |
| **Properties, not custom fields** | All design parameters live in Odoo Properties. Definitions are data, not code. |

---

## Target Industries

| Industry | Key Challenge | Example |
|---|---|---|
| Garbage bags | Resin consumption depends on geometry | Width x length x thickness x density |
| Corrugated boxes | Board grade, liner combo, trim optimization | Multi-layer grammage calculation |
| Roller shutters | Motor selected by door weight, not user choice | `motor_class = f(area x slat_weight)` |
| Security doors | RC class forces minimums on all components | `sheet_thickness = max(user, RC_min)` |
| Interior doors | Double-leaf has different geometry | `effective_area = w x h x 2` |

---

## Module Stack

```
                                    ┌──────────────────────────────────┐
                                    │   mrp_design_matrix_bags         │
                                    │   mrp_design_matrix_corrugated   │
                                    │   mrp_design_matrix_roller_door  │  Industry
                                    │   mrp_design_matrix_security_door│  Submodules
                                    │   mrp_design_matrix_interior_door│
                                    └──────────────┬───────────────────┘
                                                   │ depends
                                    ┌──────────────▼───────────────────┐
                                    │      mrp_design_matrix           │  Core Engine
                                    │  (models, views, GoRules, UI)    │
                                    └──────────────┬───────────────────┘
                                                   │ depends
                          ┌────────────────────────┼────────────────────────┐
                          │                        │                        │
           ┌──────────────▼──────┐  ┌──────────────▼──────┐  ┌──────────────▼────────────┐
           │ mrp_bom_formula_    │  │ stock_move_forced_  │  │ stock_move_forced_        │
           │ lot_dimension       │  │ lot_multi           │  │ lot_multi_dim             │
           │ (bridge ~50 lines)  │  │ (PR candidate OCA)  │  │ (width/height/thickness)  │
           └──────────────┬──────┘  └─────────────────────┘  └───────────────────────────┘
                          │ depends
           ┌──────────────▼──────────────────┐
           │ mrp_bom_line_formula_template   │  own formula engine (this repo)
           └─────────────────────────────────┘
```

---

## Design Matrix -- The Four Tables

### T0 -- Constraints

Executes **before** anything else. Blocks invalid designs or warns about risky ones.

| Type | Effect | Example |
|---|---|---|
| `ERROR` | `UserError`, stops MO creation | Perforation + insulation (roller) |
| `WARNING` | `message_post`, continues | Width > 4000mm + manual drive (roller) |

### T1 -- Geometry + Forced Values

Computes intermediate variables and enriches the context for T2/T3.

| Effect Type | Description | Example |
|---|---|---|
| `context_modify` | Computes new value | `effective_length = height x 2 + 50` |
| `context_force` | Overrides user input with minimum | `sheet_thickness = max(user, RC_min)` |
| `context_derive` | Computes from physics | `motor_class = f(area x slat_weight)` |

### T2 -- Materials

Three output types (non-exclusive):

| Type | Mechanism | Use Case |
|---|---|---|
| **O-variant activation** | `{"bom_line_coeff_key": "ink-O", "coefficient": 1.15}` | Activate/deactivate BoM line |
| **Direct ref** | `{"product_ref": "module.product_xmlid", ...}` | Fixed materials without variants |
| **PTAV resolution** | `{"product_tmpl_ref": "...", "param_attribute_map": {...}}` | Design param -> attribute -> variant |

### T3 -- Operations

Conditionally adds workorders to the MO.

```json
{"workcenter_ref": "module.wc_assembly", "duration_formula": "width * 0.5", "sequence": 10}
```

---

## Design Parameters -- Odoo Properties

All industry-specific parameters live in `fields.Properties`, following the pattern from [product_electrical_properties](https://github.com/OCA/product-attribute). Only `width`, `height`, and `thickness` remain as real fields.

### Definition (XML)

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

### Reading (Python)

```python
design_context = {
    "width": lot.width, "height": lot.height, "thickness": lot.thickness,
    "qty": production.product_qty,
    **{k: v for k, v in (lot.design_params or {}).items()},
}
# -> {"width": 600, "bag_type": "sleeve", "has_tie": True, ...}
```

---

## PTAV Resolution

Design parameters map to product attributes, enabling automatic variant selection:

```
design_params.color = "FF0000"
    | param_attribute_map: {"color": "module.attr_color"}
    v
attribute: Color / value: "FF0000"
    | _get_variant_for_combination(ptav)
    v
product.product: Ink + Color/FF0000
```

Values in `design_params` must match `product.attribute.value.name` exactly.

---

## Semi-Finished Products -- Recursive Chain

Each semi-finished product gets its own lot with parameters extracted from the parent lot:

```
End product lot_1: {bag_type, has_tie, width, color, thickness}
    MO Level 1
        |
        +-- Film (semi-finished)
        |       lot_2: {bag_type, width, color, thickness}
        |       <- extracted via param_extraction_map
        |       MO Level 2
        |            |
        |            +-- Resin  mto_stop=True -> PO
        |
        +-- Tie  mto_stop=True -> PO or stock
                lot_3: {tie_length: height + 50}
                <- transformation via safe_eval
```

| `mto_stop` | Behavior |
|---|---|
| `False` | Creates new MO + child lot, recursion continues |
| `True` | Searches stock for matching lot -> if none -> PO with parameters |

---

## Matrix Templates -- Workflow

```
1. Select design_param_definition_id on BoM  ->  lot shows correct Properties
2. Select matrix_template_id  ->  press [Load from Template]
3. Edit the 4 JSON tables with ace_editor    ->  changes are per-BoM
4. Template is NEVER edited directly
```

Templates are shipped by industry submodules. The customer copies and customizes.

---

## Data Models

### `mrp.design.param.definition`

| Field | Type | Description |
|---|---|---|
| `code` | `Char` | Unique code: `'bags'`, `'roller_door'` |
| `name` | `Char` | Human-readable name |
| `industry` | `Char` | Grouping/filtering |
| `parent_id` | `Many2one -> self` | Inheritance |
| `design_params_definition` | `PropertiesDefinition` | Parameter schema |

### `mrp.matrix.template`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Template name |
| `industry` | `Char` | For filtering |
| `constraint_table` | `Json` | T0 rules (GoRules format) |
| `geometry_table` | `Json` | T1 rules |
| `material_table` | `Json` | T2 rules |
| `operation_table` | `Json` | T3 rules |

### `mrp.bom` (extended)

| Field | Type | Description |
|---|---|---|
| `design_param_definition_id` | `Many2one` | Parameter set for this BoM |
| `matrix_template_id` | `Many2one` | Template reference (read-only) |
| `constraint_table` | `Json` | T0 -- editable copy |
| `geometry_table` | `Json` | T1 -- editable copy |
| `material_table` | `Json` | T2 -- editable copy |
| `operation_table` | `Json` | T3 -- editable copy |

### `mrp.bom.line` (extended)

| Field | Type | Description |
|---|---|---|
| `matrix_coeff_rule` | `Char` | Reference to T2 row for coefficient |
| `coeff_default` | `Float` | `0.0` = O-variant, `1.0` = real |
| `product_tmpl_id` | `Many2one` | For PTAV resolution |
| `param_attribute_map` | `Json` | `{design_key: attr_external_id}` |
| `param_extraction_map` | `Json` | `{child_key: source_or_formula}` |
| `child_definition_id` | `Many2one` | Child lot parameter set |
| `mto_stop` | `Boolean` | Stops MTO chain at this level |

### `stock.lot` (extended)

| Field | Type | Description |
|---|---|---|
| `width / height / thickness` | `Float` | Real fields (from `_dim` module) |
| `design_param_definition_id` | `Many2one` | Parameter set |
| `design_params` | `Properties` | All industry parameters |

---

## Repository Structure

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
        mrp_bom_views.xml
        mrp_matrix_template_views.xml
        mrp_design_param_definition_views.xml
    data/
        base_param_definitions.xml

mrp_design_matrix_{industry}/
    data/
        design_param_definitions.xml
        install_design_params.xml
        matrix_templates/*.json
    demo/
        demo_bom_{industry}.xml
```

---

## Technical Requirements

- **Odoo:** 18.0 (Community and Enterprise)
- **License:** AGPL-3
- **Dependencies:** OCA/Odoo CE modules only
- **Rule engine:** `zen-engine` (Rust + Python bindings, <1ms latency, embeddable)
- **Pre-commit:** `ruff`, `black`, OCA checks
- **Tests:** Required for every module

---

## Project Plan

| Phase | Duration | Key Result |
|---|---|---|
| Phase 0 -- Foundation | 2 weeks | `forced_lot` PRs in OCA |
| Phase 1 -- Bridge | 1 week | Formula module sees Properties |
| Phase 2 -- Core models | 2 weeks | All models + UI |
| Phase 3 -- Core logic | 2 weeks | Full MO algorithm end-to-end |
| Phase 4 -- Industry submodules | 3 weeks | 5 industry packages |
| Phase 5 -- OCA submission | 1 week | PR submitted |

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| OCA review requires significant changes | Medium | Early precheck with OCA maintainer |
| GoRules doesn't cover all T0 cases | Low | cDMN as fallback for constraints |
| PTAV matching requires exact name match | High | Validation on `design_params` save |
| Industry templates are incomplete | Medium | Demo data + documentation for extension |

---

## Credits

**Author:** Rosen Vladimirov \<vladimirov.rosen@gmail.com\> | Terraros Commerce Ltd.

**Inspired by:** [product_electrical_properties](https://github.com/OCA/product-attribute) (Properties pattern)

## License

This project is **dual-licensed**: [AGPL-3.0](LICENSE) by default, or a commercial license — see [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md) and [DUAL_LICENSING.md](DUAL_LICENSING.md) (contact: vladimirov.rosen@gmail.com).
