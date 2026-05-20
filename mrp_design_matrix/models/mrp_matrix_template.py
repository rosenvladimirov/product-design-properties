# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class MrpMatrixTemplate(models.Model):
    """
    Stores DMN rule tables (GoRules JSON format) for a specific industry.

    Templates are shipped read-only with each sub-module via data XML.
    The user copies them into a BoM with ``action_load_from_template()``
    and customises the copies — the original template is never edited.

    Table structure (GoRules JDM format stored as JSONB):
        - constraint_table : T0 — validation constraints (ERROR / WARNING)
        - geometry_table   : T1 — geometry & forced values
        - material_table   : T2 — material selection & quantities
        - operation_table  : T3 — conditional workorders
    """

    _name = "mrp.matrix.template"
    _description = "Design Matrix Template"
    _rec_name = "name"
    _order = "industry_id, name"

    name = fields.Char(required=True)
    industry_id = fields.Many2one(
        "design.industry",
        string="Industry",
        ondelete="restrict",
        index=True,
        help="Canonical industry classification. Resolved automatically "
        "from the data tag (e.g. industry=\"doors\") via "
        "design.industry._resolve — no data-file changes needed.",
    )
    description = fields.Text()

    # -- Zero-churn industry resolution --------------------------------------
    # 8-те sibling модула подават `<field name="industry">doors</field>` като
    # свободен стринг. Прехващаме го и резолваме към design.industry, така че
    # data файловете им остават непокътнати.

    @api.model
    def _pop_industry_tag(self, vals):
        """Translate a string ``industry`` key in *vals* to ``industry_id``."""
        if "industry" in vals and not isinstance(vals.get("industry"), int):
            tag = vals.pop("industry")
            industry = self.env["design.industry"].sudo()._resolve(tag)
            vals["industry_id"] = industry.id or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_industry_tag(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._pop_industry_tag(vals)
        return super().write(vals)

    constraint_table = fields.Json(
        "T0 — Constraints",
        help="GoRules JDM JSON: ERROR / WARNING rules evaluated before MO.",
    )
    geometry_table = fields.Json(
        "T1 — Geometry",
        help=(
            "GoRules JDM JSON: computes intermediate context variables. "
            "Supports context_modify, context_force and context_derive effects."
        ),
    )
    material_table = fields.Json(
        "T2 — Materials",
        help=(
            "GoRules JDM JSON: determines which materials enter the MO and "
            "in what quantities. Supports O-variant activation, direct ref "
            "and PTAV resolution."
        ),
    )
    operation_table = fields.Json(
        "T3 — Operations",
        help="GoRules JDM JSON: conditionally adds workorders to the MO.",
    )
