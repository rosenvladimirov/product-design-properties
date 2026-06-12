==========================================
MRP BoM Formula — Forced Lot Consumption
==========================================

.. note::
   Dual-licensed: available under AGPL-3.0-or-later (default) or under a
   commercial license from Rosen Vladimirov — see ``LICENSE-COMMERCIAL.md``
   at the repository root (contact: vladimirov.rosen@gmail.com).

.. tip::
   Българско ръководство: виж `README.bg.md <README.bg.md>`_.

Bridges ``mrp_bom_line_formula_template`` and
``stock_move_forced_lot_multi``: the BoM line formula decides **which
forced lots** a raw move consumes — and optionally **how much per lot**.

Output variable
===============

::

    forced_lots = lot_model.search([...])      # recordset
    forced_lots = [lot_a, lot_b]               # list
    forced_lots = {lot_a: 3.0, lot_b: 1.0}     # lot → exact quantity

- list/recordset → the move's ``forced_lot_ids`` is set; the base
  module's reservation fills the move lines (pro-rata for multiple lots);
- dict → additionally stores the per-lot quantities and applies them on
  reservation **instead of** the pro-rata split.

Extra context
=============

- ``lot_model`` — the ``stock.lot`` model (search/browse);
- ``mo_forced_lots`` — the MO's forced lots filtered to the line's
  product;
- everything from the base formula engine (``production``, ``env``,
  design parameters, ...).

Example
=======

Consume from the lot matched by the design width, exact split::

    result = width / 1000 * 4
    main = lot_model.search([('product_id', '=', product.id),
                             ('name', 'ilike', 'W%d' % int(width))], limit=1)
    rest = mo_forced_lots - main
    forced_lots = {main: result - 1, rest: 1} if rest else [main]

Notes
=====

- the matrix path (``mrp_design_matrix``) keeps its own child-lot /
  matching mechanism — this module covers the standard explosion;
- install manually (no auto_install), needs both parent modules on the
  addons path (``stock_move_forced_lot_multi`` lives in the
  ``manufacture`` repository).
