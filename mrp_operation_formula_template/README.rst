================================
MRP Operation Formula Templates
================================

.. note::
   Dual-licensed: available under AGPL-3.0-or-later (default) or under a
   commercial license from Rosen Vladimirov — see ``LICENSE-COMMERCIAL.md``
   at the repository root (contact: vladimirov.rosen@gmail.com).

.. tip::
   Българско ръководство: виж `README.bg.md <README.bg.md>`_.

Extends ``mrp_bom_line_formula_template`` to the **operations** (work
orders) of a BoM. An operation can carry a formula template whose Python
code controls, per manufacturing order:

1. the **expected duration** of the work order (minutes);
2. whether the operation **exists at all** in this MO (``skip``);
3. **which raw materials are consumed** at this work order.

Install manually where operations/work orders are actually used — the
module is intentionally not auto-installed, and it is a no-op until an
operation carries a formula.

Usage
=====

1. *Manufacturing → Configuration → Formula Templates* — create a
   template (the same library used for BoM lines);
2. open the BoM operation → **Operation Formula** section → pick the
   template;
3. the formula runs for every MO at confirmation time.

Output variables
================

================================  =====================================================
Variable                          Effect
================================  =====================================================
``result`` (or ``duration``)      expected duration in minutes
``skip = True``                   drop this operation's work order from the MO entirely
``collect_materials = True``      consume all still-unassigned raw moves here
``materials = [products]``        consume the raw moves of those products here
``employee`` / ``employees``      assign operator(s) to the work order (EE fields)
================================  =====================================================

``duration`` enters the context **initialized with the standard value**
(Odoo's time_cycle computation), so relative adjustments work::

    result = duration * 1.2      # +20% over the standard

Evaluation context
==================

``operation``, ``workcenter``, ``production``, ``workorder``,
``product``, ``product_qty``, ``duration``, ``env``,
``employee_model`` (``hr.employee``, when HR is installed),
``employees`` (the work center's available operators), plus the design
parameters (``width``, ``height``, ...) of the producing lot when
``mrp_design_matrix`` is installed (T3 integration), and the full
``design_context`` dict.

Examples
========

Area-driven duration (design matrix)::

    result = 10 + (width * height / 1e6) * 2.5

Conditional operation — lacquering only when a coating is ordered::

    skip = not has_coating
    result = duration

Operation consumes specific materials::

    result = 20
    materials = [env.ref('my_module.product_glue'),
                 env.ref('my_module.product_screws')]

First operation collects all raw materials (matrix-T3 style)::

    result = duration
    collect_materials = True

Assign an operator by skill/name (Enterprise operator fields)::

    result = duration
    employees = employee_model.search([('name', 'ilike', 'welder')], limit=2)

Error behaviour
===============

An exception inside the formula, or a non-numeric result, logs a
**warning** and keeps the standard behaviour (standard duration, the
operation stays, materials untouched). A broken formula never blocks
the MO.

Technical notes
===============

- Hooks: ``mrp.workorder._get_duration_expected()`` (duration) and a
  post-pass in ``mrp.production.action_confirm()`` (skip / materials);
- material assignment relies on ``stock.move.workorder_id`` (core mrp),
  guarded by a ``_fields`` check;
- v18 ``lot_producing_id`` / v19+ ``lot_producing_ids`` are detected
  automatically — the same code runs on 18/19/20;
- the manifest stays ``license: AGPL-3`` (Odoo has no "dual" enum
  value) — the commercial offer lives in the file headers and the
  repository-root documents.
