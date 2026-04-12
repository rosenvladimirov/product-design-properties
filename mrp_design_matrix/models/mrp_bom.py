# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    matrix_template_id = fields.Many2one(
        "mrp.matrix.template",
        string="Matrix Template",
        help=(
            "Reference to the source template. "
            "Use 'Load from Template' to copy the four rule tables. "
            "Editing the tables below does NOT affect the template."
        ),
    )

    # ── Rule tables (JSONB copies owned by this BoM) ─────────────────────

    constraint_table = fields.Json(
        "T0 — Constraints",
        help="GoRules JDM. Evaluated before MO confirmation.",
    )
    geometry_table = fields.Json(
        "T1 — Geometry",
        help="GoRules JDM. Produces intermediate context variables.",
    )
    material_table = fields.Json(
        "T2 — Materials",
        help="GoRules JDM. Produces (product, qty, uom, coeff) rows.",
    )
    operation_table = fields.Json(
        "T3 — Operations",
        help="GoRules JDM. Produces conditional workorders.",
    )

    variant_context_map = fields.Json(
        "Variant → Context Map",
        help=(
            "Maps design context keys to product attribute names. "
            "When generating moves, the MO product variant's attribute "
            "values are injected into the design context using this map.\n"
            'Example: {"coating": "Покритие (SolidDoor)"}'
        ),
    )

    # ── Actions ──────────────────────────────────────────────────────────

    def action_load_from_template(self):
        """Copy the four rule tables from ``matrix_template_id`` into this BoM."""
        self.ensure_one()
        if not self.matrix_template_id:
            return
        t = self.matrix_template_id
        self.write(
            {
                "constraint_table": t.constraint_table,
                "geometry_table": t.geometry_table,
                "material_table": t.material_table,
                "operation_table": t.operation_table,
            }
        )
