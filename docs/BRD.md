# MRP Design Matrix — Business Requirements Document (BRD)

**Version:** 1.0 | **Date:** March 2026 | **Author:** Rosen Vladimirov \<vladimirov.rosen@gmail.com\> | BL Consulting | Odoo Silver Partner

---

## 1. Executive Summary

Manufacturing enterprises in Bulgaria and the region operating on a make-to-order basis face a fundamental problem in Odoo: the standard system manages products as categories but cannot describe the specific physical item that needs to be produced right now, for this exact customer, with these exact parameters.

The result is twofold: the engineering department maintains thousands of product variants in the system (one for each combination of parameters), or — worse — relies on paper-based specifications outside the system. In both cases, planning, traceability, and costing are incomplete.

**MRP Design Matrix** solves this problem by introducing a new conceptual layer: the production lot (batch) carries the design specification of the item. The recipe (BoM) is parametric — materials and quantities are calculated automatically from the lot parameters. A system of rules (matrix) governs this transformation.

---

## 2. Context and Problem Statement

### 2.1 Target Industries

The solution is designed as a universal model applicable to manufacturers in the following sectors:

| Industry | Specifics | Key Problem |
|---|---|---|
| Garbage bags | Tube/sheet, various thicknesses and sizes | Resin consumption depends on geometry |
| Corrugated boxes | Board grade, flute type, liner combo | Trim optimization, roll stock planning |
| Roller shutters | Slat, drive mechanism, insulation | Motor is selected based on door weight |
| Security doors | RC class as master parameter | RC class enforces minimums on all components |
| Interior doors | Construction, finish, frame | Double-leaf doors have different geometry |

### 2.2 Pain Points

- The standard Odoo variant cannot carry a production specification — it is a category, not a physical object
- BoM lines have fixed quantities — they do not depend on the dimensions or parameters of a specific order
- There is no mechanism for conditional inclusion of materials ("if printing is required, add ink")
- Invalid parameter combinations are not blocked automatically ("perforation + insulation" is physically impossible)
- Raw material and semi-finished goods planning cannot follow the chain downstream
- Traceability from the finished product to the raw material lot is incomplete

---

## 3. Business Objectives

1. Eliminate manual entry of technical specifications outside the system
2. Automatic calculation of material requirements based on the physical parameters of the item
3. Full traceability from the finished product to the raw material lot at every level of the production chain
4. Automatic design validation before starting production
5. Procurement planning for raw materials linked to the actual parameters of orders
6. A universal model applicable across different industries without changing the core

---

## 4. Functional Requirements

### 4.1 Design Parameters

The system must allow the description of an arbitrary set of typed parameters for each specific production run:

- **Numeric:** width, height, thickness, density, grammage
- **Text:** color (RAL code), reference, article number
- **Boolean:** has printing, has reinforcement, has insulation
- **Selection:** bag type (tube/sheet), RC class, finish type

Parameters must be configurable through the user interface without code changes. Different types of products have different sets of parameters. The system must support inheritance (base set + extensions).

### 4.2 Parametric Recipe (BoM)

The recipe must support:

- Fixed materials with quantity calculated by a formula from the design parameters
- **O-variants** (conditional materials): present for MRP planning but included in MO only if the condition is met
- Dynamic selection of a specific material variant through parameter matching (PTAV)
- A scaling coefficient for quantity and price simultaneously

### 4.3 Rule System (Matrix)

The matrix contains four types of tables:

| Table | Description |
|---|---|
| **T0 — Constraints** | Blocks invalid combinations before production. Two types: error (stops MO) and warning (informs). |
| **T1 — Geometry** | Calculates derived parameters. Can enforce minimum values (RC class). |
| **T2 — Materials** | Determines which materials are used and in what quantities. Three mechanisms: O-variant, direct selection, selection by parameters. |
| **T3 — Operations** | Determines which manufacturing operations are executed conditionally. |

### 4.4 Semi-Finished Products and Production Chain

- Each semi-finished product receives its own lot with **extracted parameters** from the parent item
- Extraction is configured at the recipe level: which parameters are passed downstream and how
- Parameters can be transformed during handoff (example: length is extended by 50 mm for the joint)
- The **MTO Stop** flag controls whether the chain continues downstream or stops with a stock lookup

### 4.5 Templates

- The system ships ready-made templates with rules for each industry
- The customer copies the template and adapts it — the original is not modified
- Templates are loaded into the recipe with a single button

---

## 5. Non-Functional Requirements

- Compatibility with Odoo 18 Community and Enterprise
- AGPL-3 license, published in OCA (Odoo Community Association)
- No dependencies on paid libraries at runtime
- Matrix processing during MO creation under 2 seconds
- Support for standard Odoo functionalities: MRP planning, costing, traceability

---

## 6. Out of Scope

- Trim optimization for corrugated board (scheduling layer — separate project)
- Integration with machine systems (SCADA, PLC)
- Mobile interface for operators
- BI reports and dashboards

---

## 7. Stakeholders

| Role | Interest | Influence |
|---|---|---|
| Production Director | Accurate planning, no manual corrections | High |
| Process Engineer | Easy entry of design specifications | High |
| Accountant | Accurate costing per batch | Medium |
| Warehouse Clerk | Clear traceability of raw materials | Medium |
| IT Administrator | Easy maintenance, no custom code | Medium |
| Manufacturer's Customer | Timely delivery, quality | Low (indirect) |
