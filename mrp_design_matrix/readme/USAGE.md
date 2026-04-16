**Triggering the matrix engine:**

The engine runs automatically in `action_confirm()` of any MO whose
BoM has a non-empty `constraint_table`.  No explicit invocation is
needed.

**Flow:**

1.  Matrix engine reads `lot_producing_ids[:1]._get_design_context()` to
    build a flat dict of all design parameters (first lot is the design lot).
2.  T0 evaluation — errors raise `UserError`, warnings post on the MO
    chatter.
3.  T1 evaluation — geometry outputs override the context (they take
    precedence over user-supplied values).
4.  BoM line iteration — `qty_formula × matrix_coeff` determines the
    final raw move quantity.  O-variants with `coeff_default=0.0` are
    skipped unless the matrix activates them.
5.  T2 ad-hoc rows — adds moves for products not listed on the BoM
    lines (direct ref or PTAV).
6.  T3 evaluation — creates workorders for matching operations.
7.  Semi-finished chain — spawns child lots or stops at existing
    stock lots depending on `mto_stop`.

**Testing without creating an MO:**

Click the _Matrix Rules_ smart button on the BoM form.  The preview
dialog loads the BoM's parameter definition, lets you move sliders and
toggle options, and shows T0/T1/T2/T3 evaluation results in real time.
