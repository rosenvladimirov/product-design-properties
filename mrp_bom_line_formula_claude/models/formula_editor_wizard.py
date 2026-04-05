# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models

CLAUDE_INSTRUCTIONS = """\
# BoM Line Quantity Formula — Generation Task

You are helping the user write a quantity formula for an Odoo BoM line.
The user wants to express how much of a component is consumed per MO.

## How to work

1. Read this wizard record to get context:
   odoo_read("mrp.bom.line.formula.wizard", [<res_id>],
             ["bom_line_id", "product_name", "quantity_formula", "claude_brief"])

2. The `claude_brief` field contains a JSON block with:
   - BoM line info (product, UoM)
   - The parent BoM (product template)
   - Which matrix tables exist (T0/T1/T2/T3)
   - Design parameter definition (names, types, defaults)
   - The current formula (if any)

3. Ask the user what formula they want (in plain Bulgarian or English).

4. Generate the formula following these rules:

   Input variables available in the formula:
   - `bom_line`, `production`, `product`, `product_uom`, `product_uom_qty`, `operation`
   - `env` (Odoo environment — use env.ref(), env['model'].search())
   - When called from design matrix: width, height, thickness, and all T1
     geometry outputs and design params as flat variables
   - `design_context` (full dict)

   Output variables (set in the formula):
   - `result` (required) — computed quantity, float
   - `product` (optional) — override the BoM line product via env.ref()
   - `uom` (optional) — override the UoM via env.ref()

5. Show the formula to the user and ask for confirmation.

6. Write the formula back via RPC:
   odoo_write("mrp.bom.line.formula.wizard", [<res_id>],
              {"quantity_formula": "<generated formula>"})

7. Call odoo_refresh so the UI reloads and the user sees the formula:
   odoo_refresh(model="mrp.bom.line.formula.wizard", res_id=<res_id>)

## Examples

```python
# Simple multiplier
result = product_uom_qty * 1.05
```

```python
# Area-based (requires design matrix with width/height params)
result = (width / 1000) * (height / 1000)
```

```python
# Product override by design param
result = 1
if construction == "glass":
    product = env.ref("my_module.glass_panel_product")
    uom = env.ref("uom.product_uom_unit")
```

Stay conversational. Confirm before writing.
"""


class FormulaEditorWizard(models.TransientModel):
    _inherit = "mrp.bom.line.formula.wizard"

    claude_brief = fields.Text(
        compute="_compute_claude_brief",
        string="Claude Context",
        help="JSON context that Claude reads to understand the task.",
    )
    claude_instructions = fields.Text(
        default=CLAUDE_INSTRUCTIONS,
        readonly=True,
        help="Static task description for Claude.",
    )
    claude_trigger = fields.Integer(
        default=0,
        help="Trigger field for the Ask Claude button widget.",
    )

    @api.depends("bom_line_id", "quantity_formula")
    def _compute_claude_brief(self):
        for wiz in self:
            wiz.claude_brief = json.dumps(
                wiz._build_claude_brief(),
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    def _build_claude_brief(self):
        """Build a structured context dict for Claude."""
        self.ensure_one()
        line = self.bom_line_id
        if not line:
            return {"error": "No BoM line linked to wizard."}

        bom = line.bom_id
        brief = {
            "task": "generate_bom_line_quantity_formula",
            "wizard": {
                "id": self.id,
                "model": "mrp.bom.line.formula.wizard",
            },
            "bom_line": {
                "id": line.id,
                "product": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom": line.product_uom_id.name,
                "product_uom_id": line.product_uom_id.id,
                "product_qty": line.product_qty,
                "current_formula": (
                    self.quantity_formula or line.quantity_formula or None
                ),
            },
            "bom": {
                "id": bom.id,
                "code": bom.code or "",
                "product_tmpl": bom.product_tmpl_id.name,
                "product_qty": bom.product_qty,
            },
            "matrix_tables": {
                "constraint": bool(getattr(bom, "constraint_table", False)),
                "geometry": bool(getattr(bom, "geometry_table", False)),
                "material": bool(getattr(bom, "material_table", False)),
                "operation": bool(getattr(bom, "operation_table", False)),
            },
            "design_params": [],
        }

        definition = getattr(bom, "design_param_definition_id", False)
        if definition:
            defn_list = (
                getattr(definition, "full_design_params_definition", None)
                or getattr(definition, "design_params_definition", None)
                or []
            )
            for prop in defn_list:
                brief["design_params"].append(
                    {
                        "name": prop.get("name"),
                        "string": prop.get("string"),
                        "type": prop.get("type"),
                        "default": prop.get("default"),
                        "selection": prop.get("selection"),
                    }
                )

        # BoM line coefficient fields from mrp_design_matrix
        if hasattr(line, "coeff_default"):
            brief["bom_line"]["coeff_default"] = line.coeff_default
            brief["bom_line"]["matrix_coeff_rule"] = line.matrix_coeff_rule or ""

        return brief
