# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] - 2026-07-13

### Added

- Initial release: domain-agnostic formula kernel extracted as a
  generic sibling of the `mrp_bom_line_formula_template` evaluation
  core (rewrite, no code moved — the MRP module stays untouched and
  may migrate onto this kernel later).
- `formula.engine.mixin` (AbstractModel): `_formula_check` /
  `_formula_validate` (syntax validation via `test_python_expr`,
  forbidden dunder names surfaced as validation messages instead of
  raw NameError), `_formula_eval` (safe_eval exec over a caller-built
  context with a declared-outputs contract and an opt-in `strict`
  mode that clears declared outputs pre-eval and raises on a missing
  one — stale values from a reused context can never pass as
  results) and the `_formula_eval_context` extension hook (returned
  extra symbols are merged back so the in-place context contract
  always holds). No built-in error policy — exceptions propagate and
  each consuming domain decides (MRP: fallback; payroll: hard fail).
- `formula.template`: reusable, multi-company formula records with
  `code` lookup (company-specific record wins over the global one,
  resolved with `with_company` so explicit cross-company resolution
  cannot silently fall back to the global record), `usage` tag,
  syntax validation on write and an `evaluate()` convenience wrapper.
  `code` is `copy=False`; uniqueness is enforced both per company and
  for global records (partial unique index — PostgreSQL treats NULL
  as distinct in plain UNIQUE constraints).
- Security: read for internal users, write for `base.group_system`
  only (formulas are code execution — see CONTEXT.md for the trust
  boundary), multi-company record rule.

*Assisted by Claude Code*
