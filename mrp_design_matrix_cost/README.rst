MRP Design Matrix — Cost & Price
================================

Financial engine for the design-matrix stack: rolls up **material + labour
cost** for a parametric BoM configuration and derives a **suggested sale
price** (markup) — read-only, it never writes prices or creates records.

How it computes
---------------

``mrp.bom.simulate_design_cost(design_context)``:

1. **T1 geometry** (optional JDM table) enriches the context.
2. **Materials**: for every BoM line — ``quantity_formula`` (or static qty)
   × T2 matrix coefficient × (1 + ``loss``), priced at ``standard_price``
   (fallback: last confirmed purchase price, marked "ПО"). Components with
   their own BoM are **recursed** (depth ≤ 5) — the sub-BoM total is the
   unit cost. ``material_choice`` selections from the configurator resolve
   to the real variant.
3. **Labour (T3)**: the JDM ``operation_table`` returns rows of
   ``workcenter_code`` + ``duration_min``; cost = minutes/60 × the work
   center's ``costs_hour``. Work centers are read with ``sudo()`` —
   they are company-specific and must price identically for all companies.
4. **Sale**: ``material × (1+material_markup%) + labour × (1+labour_markup%)``
   (markups on the product template) + pricelist percentage discount.

Access model
------------

* ``simulate_cost_for_product`` (the configurator's live calculation) is
  available to **all internal users** but **redacted** for non-managers:
  they receive only the sale part, never cost/margin.
* The full breakdown requires the **Design / Manager (Cost)** group
  (``group_design_manager``) — enforced server-side, not just in the UI.
* Portal/public users are rejected.

Trust rails (D2)
----------------

* Evaluation errors are **never swallowed**: the result carries
  ``errors`` / ``incomplete`` / ``error`` and the configurator shows
  "cost is INCOMPLETE" instead of a plausible-but-wrong number.
* A daily **sentinel cron** simulates reference configurations
  (``ir.config_parameter`` ``mrp_design_matrix_cost.sentinel_checks``)
  and alerts managers (chatter + activity) when totals drift outside
  tolerance or labour/material/operations fall below their floor.
* The financial engine is covered by tests (``tests/test_simulate_cost.py``).

Upgrade notes (v19 → v20)
-------------------------

* The rule tables are JSONB (GoRules JDM). Legacy "flat" tables are
  normalized on write and by the ``mrp_design_matrix`` migration; keep
  ``base_zen_decision.normalize_jdm_graph`` in the upgrade path.
* ``standard_price`` is company-dependent — any price-loading code must
  write per company (see the solid_door loader).

License: AGPL-3.0-or-later or commercial (see LICENSE-COMMERCIAL.md).
