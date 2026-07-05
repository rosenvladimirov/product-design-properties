# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
from odoo import _, api, fields, models
from odoo.addons.base_zen_decision.models.zen_engine import (
    normalize_jdm_graph,
    validate_graph,
)
from odoo.exceptions import ValidationError


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

    _RULE_TABLE_FIELDS = ("constraint_table", "geometry_table",
                          "material_table", "operation_table")

    @api.model
    def _pop_industry_tag(self, vals):
        """Translate a string ``industry`` key in *vals* to ``industry_id``."""
        if "industry" in vals and not isinstance(vals.get("industry"), int):
            tag = vals.pop("industry")
            industry = self.env["design.industry"].sudo()._resolve(tag)
            vals["industry_id"] = industry.id or False
        return vals

    @api.model
    def _normalize_rule_tables(self, vals):
        """Zero-churn нормализация (D2): заварените data файлове подават
        „плосък" формат ({'nodes':[{type:'decisionTable'}]}, без edges) —
        zen-engine го приема МЪЛЧАЛИВО и връща [] за всеки контекст
        (T3=[] инцидентът). Опаковаме го в пълен JDM граф при запис;
        data файловете остават непокътнати (както industry tag-а)."""
        for fname in self._RULE_TABLE_FIELDS:
            if vals.get(fname):
                vals[fname] = normalize_jdm_graph(vals[fname])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_industry_tag(vals)
            self._normalize_rule_tables(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._pop_industry_tag(vals)
        self._normalize_rule_tables(vals)
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

    @api.constrains("constraint_table", "geometry_table",
                    "material_table", "operation_table")
    def _check_rule_tables(self):
        """Write-time валидация на шаблонните T0-T3 графи (D2) — както на
        BoM-а: счупен граф не бива да влиза тихо и после да се копира в
        десетки BoM-ове през action_load_from_template."""
        labels = {
            "constraint_table": "T0 (Constraints)",
            "geometry_table": "T1 (Geometry)",
            "material_table": "T2 (Materials)",
            "operation_table": "T3 (Operations)",
        }
        for rec in self:
            problems = []
            for fname, label in labels.items():
                # валидира се НОРМАЛИЗИРАНАТА стойност: заварен плосък
                # формат е ЛЕЧИМ (migration/write hook го опакова) и не бива
                # да блокира write на съседно поле на жива база.
                problems += ["%s: %s" % (label, e)
                             for e in validate_graph(
                                 normalize_jdm_graph(rec[fname]))]
            if problems:
                raise ValidationError(
                    _("Invalid rule table on template %(tmpl)s:\n- %(problems)s",
                      tmpl=rec.display_name,
                      problems="\n- ".join(problems)))
