================================
MRP Operation Formula Templates
================================

.. note::
   Dual-licensed: available under AGPL-3.0-or-later (default) or under a
   commercial license from Rosen Vladimirov — see ``LICENSE-COMMERCIAL.md``
   at the repository root (contact: vladimirov.rosen@gmail.com).

Extends ``mrp_bom_line_formula_template`` to the **operations** (work
orders) of a BoM. An operation can carry a formula template whose code
controls, per manufacturing order:

- ``result`` / ``duration`` — the expected duration in minutes
  (``duration`` is initialized with the standard value, so relative
  adjustments like ``result = duration * 1.2`` work);
- ``skip = True`` — the operation's work order is dropped from the MO
  entirely (conditional operations);
- ``collect_materials = True`` — all still-unassigned raw moves are
  consumed at this work order;
- ``materials = [products]`` — the raw moves of those products are
  consumed at this work order.

The evaluation context mirrors the BoM-line engine: ``operation``,
``workcenter``, ``production``, ``workorder``, ``product``,
``product_qty``, ``env``, plus the design parameters (``width``,
``height``, ...) when a design lot is attached (``mrp_design_matrix``
T3 integration).

Install manually where operations/work orders are actually used —
the module is intentionally not auto-installed.
