# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    # ── O-variant coefficient ─────────────────────────────────────────────

    coeff_default = fields.Float(
        "Default Coefficient",
        default=1.0,
        help=(
            "0.0 = O-variant: present in BoM for MRP planning, "
            "skipped in MO unless the matrix activates it (coeff > 0). "
            "1.0 = always active."
        ),
    )
    matrix_coeff_rule = fields.Char(
        "Matrix Coefficient Rule",
        help=(
            "Reference key inside the T2 material table that returns "
            "the runtime coefficient for this BoM line."
        ),
    )

    # ── PTAV resolution ───────────────────────────────────────────────────

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Base Product Template",
        help=(
            "When set together with param_attribute_map, the system resolves "
            "the concrete product.product variant via PTAV at MO time. "
            "product_id then acts as the O-variant placeholder for MRP."
        ),
    )
    param_attribute_map = fields.Json(
        "Parameter → Attribute Map",
        help=(
            "JSON: {design_param_key: product_attribute_external_id}. "
            "Example: {\"color\": \"module.attr_color\"}. "
            "Values in design_params must match product.attribute.value.name."
        ),
    )

    # ── Semi-finished product chain ───────────────────────────────────────

    param_extraction_map = fields.Json(
        "Parameter Extraction Map",
        help=(
            "JSON: {child_key: source}. "
            "source = parent param key (direct copy) "
            "or a safe_eval expression against the parent lot context. "
            "Example: {\"tie_length\": \"height + 50\", \"color\": \"color\"}."
        ),
    )
    child_definition_id = fields.Many2one(
        "design.param.definition",
        string="Child Design Parameter Set",
        help=(
            "The design.param.definition assigned to the child lot "
            "created for this semi-finished component."
        ),
    )
    mto_stop = fields.Boolean(
        "MTO Stop",
        default=False,
        help=(
            "Stop the MTO chain at this level. "
            "The system looks for a matching stock lot instead of "
            "creating a new manufacturing order."
        ),
    )
