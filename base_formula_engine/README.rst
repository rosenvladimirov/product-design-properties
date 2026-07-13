===================
Base Formula Engine
===================

Domain-agnostic formula kernel: reusable formula templates plus a safe
evaluation mixin (``safe_eval``, exec mode, declared-outputs contract).

The kernel knows nothing about the consuming domain: callers build the
evaluation context and declare the output variables they care about.
There is intentionally **no built-in error policy** — exceptions
propagate and each consumer decides (fall back or fail hard).

Usage
=====

.. code-block:: python

    outputs = self.env["formula.engine.mixin"]._formula_eval(
        "result = base * rate",
        {"base": 1000.0, "rate": 0.1},
    )
    # -> {"result": 100.0}

Reusable templates live in ``formula.template`` (multi-company, code
lookup with company-specific priority, syntax validation on write).

Security note: formulas are executable code — see ``CONTEXT.md`` for
the trust boundary. Template write access is restricted to
``base.group_system``.

License
=======

Dual license: AGPL-3.0-or-later, or a commercial license from
Rosen Vladimirov (see ``LICENSE-COMMERCIAL.md`` in the repository root).
