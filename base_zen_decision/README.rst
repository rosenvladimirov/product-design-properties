Base ZEN Decision
=================

Domain-agnostic host for **GoRules ZEN** (JDM) decision graphs — the rule
engine behind the design-matrix stack (T0 constraints, T1 geometry,
T2 materials, T3 operations).

What lives here
---------------

* ``ZenRunner`` (``models/zen_engine.py``) — stateless evaluator over the
  ``zen-engine`` Python package. ``ZenWrapper`` is a deprecated alias.
* ``validate_graph(graph)`` — structural JDM validation (missing
  input/output nodes, ghost edges, disconnected tables, rules without
  columns). Returns a list of errors; empty = valid. Wired as
  ``@api.constrains`` on the four rule tables of ``mrp.bom`` and
  ``mrp.matrix.template`` so a silently-broken graph can no longer be
  saved (the "T3 returns [] for every context" incident class).
* ``normalize_jdm_graph(graph)`` — upgrades the legacy "flat" format
  (``{'nodes': [{'type': 'decisionTable'}]}`` with no edges — accepted
  silently by zen-engine but returning ``[]`` for every context) into a
  full 3-node graph. Applied on create/write and by a data migration, so
  shipped data files stay untouched (zero-churn).
* ``zen.decision.table`` — a versioned, auditable registry of decision
  graphs (publish/rollback, per-company resolution, append-only decision
  log). **Note:** the matrix stack stores its tables on the BoM itself
  (close-to-Odoo design); this registry is an optional shared library for
  cross-BoM rules, not a required layer.

Operational notes
-----------------

* If ``zen-engine`` is not installed the wrapper raises a clear UserError;
  the system parameter ``mrp_design_matrix.allow_missing_zen_engine=1``
  turns evaluation into a no-op (**never in production** — T0 constraints
  stop being enforced).
* An **empty** decision table (0 rules) is allowed by validation — the UI
  "Create Table" flow starts from zero and an empty table deceives no one;
  only structurally broken graphs are rejected.
* ``zen.decision.log`` grows unbounded by design (forensics); schedule a
  retention job if volume becomes a concern.

License: LGPL-3.0-or-later or commercial (see LICENSE-COMMERCIAL.md).
