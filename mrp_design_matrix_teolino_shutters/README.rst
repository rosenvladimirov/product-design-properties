==============================================
MRP Design Matrix — Teolino Shutters (5 models)
==============================================

Full parametric design matrix for the Teolino roller-shutter range.
Sibling of ``mrp_design_matrix_roller_door`` (which ships a single
simplified template); this module encodes the **five real Teolino
models** in one model-aware T0-T3 template — no variant explosion,
no five separate templates.

Models covered
==============

Standard, Round, T-Roll, Built-In, Thermo Comfort.

``shutter_model`` is a decision-table input; per-model constraints live
in T0 and per-model geometry in T1.

Parameters
==========

Inherited from ``base_dimensions``: ``width`` (L), ``height`` (H) in mm.

Module-specific: ``shutter_model``, ``box_size``, ``slat_size``,
``axis_size``, ``control_type``, ``guide_type``, ``shutter_count``.

Rule source
===========

All formulas/offsets are transcribed from the project knowledge base
``project_odoo_teolino.md`` (the ``bom_engine.py`` prototype; 17 locked
production samples across the 5 models).

Verified vs TBD
===============

Verified (per the locked samples):

* Per-model slat/terminal/axis/box offsets (T1).
* Slat-count modes: ``std`` ``floor((H-Box/2)/S)-1``; ``builtin``
  ``ceil(H/S)-1``; ``thermo`` ``floor((H-Box/2)/S)+(1 if S==50)``.
* Caps modes: Standard/Round/T-Roll ``n+1``; Built-In ``=n``;
  Thermo direct.
* Control kits as O-variants; Thermo motor = RS100 IO; feather guide
  Thermo-only.

TBD (not in the catalogue/prototype yet — handled as warnings, not
hard limits):

* Full ``H_MAX`` table per ``(model, box, slat, axis)`` (max ever
  2800; T-Roll Lamella 50 ``H_MAX``). T0 enforces the global L/H
  limits and warns when ``H > 2800``.
* Exact verified Odoo SKU numbers — demo products use descriptive
  placeholders (indicative code in the name), same convention as
  ``mrp_design_matrix_roller_door``. The real SKU mapping is owned by
  the downstream ``teolino_shutters_bom`` (Vladimir/Lyubomir).

Known limitations
=================

* **``industry`` tag → ``design.industry``.** This module's data files
  still declare ``industry="doors"`` as a plain string (zero-churn
  convention). Since ``design_param_base`` 18.0.1.1.0 /
  ``mrp_design_matrix`` 18.0.1.8.0 that string is auto-resolved to the
  canonical ``design.industry`` record via ``design.industry._resolve``
  (full-normalization alias map; ``doors`` → ``doors``). No data-file
  change is needed here.
* **Demo BoM xml-id / table-copy fragility (repo-wide).** The demo
  follows the established sibling convention
  (``ref="<module>.<code>"`` for ``design_param_definition_id`` and
  ``eval="ref('tmpl').constraint_table"`` for the four tables).
  ``design.param.definition.create_design_param_definitions`` does not
  register ``ir.model.data``, and Odoo 18 ``ref()`` in eval returns an
  ``int`` — so this convention is technically fragile in stock Odoo
  (``bags`` even stubs ``material_table`` to ``{}``). Mirrored here as-is
  for consistency with the reference module; fixing it properly is a
  separate ecosystem task, not specific to this module.

License
=======

AGPL-3. Copyright 2026 BL Consulting.
