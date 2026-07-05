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

    # ── Loss / waste ratio (фира) — Теолино патърн ────────────────────────
    loss = fields.Float(
        "Loss ratio",
        default=0.0,
        help=(
            "Waste/scrap fraction added on top of the geometric quantity "
            "(0.05 = 5%). Real consumption and cost include the waste: "
            "qty_with_loss = qty * (1 + loss)."
        ),
    )

    # ── Explicit material choices (configurator selectors) ────────────────

    material_choice_ids = fields.Many2many(
        "product.product",
        "mrp_bom_line_material_choice_rel",
        "bom_line_id",
        "choice_product_id",
        string="Material Choices",
        help=(
            "Explicit list of real products the user may pick for this "
            "placeholder slot in the configurator. The chosen product "
            "replaces product_id on the raw move at MO time."
        ),
    )
    material_choice_label = fields.Char(
        "Material Choice Label",
        help="Slot label shown in the configurator (e.g. 'Обков').",
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
            'Example: {"color": "module.attr_color"}. '
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
            'Example: {"tie_length": "height + 50", "color": "color"}.'
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
