## Trust boundary — formula authors have admin-level ORM access

Formulas are evaluated with Odoo's `safe_eval(mode="exec")` with the
full `env` environment exposed as a global.  This is intentional — it
lets formulas call `env.ref()`, search records, and override the BoM
line product or UoM at MO creation time.

**Security implications:**

- A formula template author can write Python that has the same ORM
  reach as the user who eventually confirms the Manufacturing Order.
- `safe_eval` blocks attribute access starting with `_` and hard-coded
  dangerous builtins (`__import__`, `exec`, `compile`), but it does
  NOT prevent calls to `.sudo()` or raw SQL via `env.cr.execute`.
- Therefore, **formula template authors must be trusted** to the same
  level as Odoo administrators.

**Enforcement in this module:**

- Read access to `mrp.bom.line.formula.template` → `mrp.group_mrp_user`
- Write / create / delete → `mrp.group_mrp_manager` only
- A multi-company `ir.rule` isolates templates by `company_id`

**Operational recommendations:**

1.  Add the `mrp.group_mrp_manager` group only to trusted staff.
2.  Treat formula edits the same way as server-action edits: review
    in code-review, track in git, never paste code from untrusted
    sources.
3.  If you need a weaker trust boundary (e.g. customer-facing
    configurators), build a separate sandbox on top — do not expose
    this module to untrusted users.
