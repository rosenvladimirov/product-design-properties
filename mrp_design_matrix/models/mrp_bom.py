# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
    cascade_table = fields.Json(
        "TΦ — Cascade Resolutions",
        help=(
            "GoRules JDM. Reactive value propagation rules consumed by the "
            "design configurator (sale_design_configurator). При празно — "
            "fallback на ``matrix_template_id.cascade_table``."
        ),
    )
    multiplicity_table = fields.Json(
        "TΩ — Multiplicity",
        help=(
            "GoRules JDM. Declarative multi-instance metadata. При празно — "
            "fallback на ``matrix_template_id.multiplicity_table``."
        ),
    )
    lookup_tables = fields.Json(
        "Lookup Tables",
        help=(
            "Named lookup tables за TΦ `derive_expression` rules. При празно — "
            "fallback на ``matrix_template_id.lookup_tables``."
        ),
    )
    availability_table = fields.Json(
        "TΠ — Param Availability",
        help=(
            "GoRules JDM. Reactive UI control table consumed by the design "
            "configurator (sale_design_configurator). При празно — fallback "
            "на ``matrix_template_id.availability_table``."
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
                "availability_table": t.availability_table,
                "cascade_table": t.cascade_table,
                "multiplicity_table": t.multiplicity_table,
                "lookup_tables": t.lookup_tables,
            }
        )

    # ── T2 wiring sanity check ──────────────────────────────────────────
    # T2 material_table emit-ва `bom_line_coeff_key` стойности (rope-o,
    # motor-o, …), които mrp.bom.line.matrix_coeff_rule трябва да декларира
    # за да получат runtime coefficient. Без декларация — coeff lookup-ът
    # отива в нищото (виж project_mrp_design_matrix_dev_teo_audit_20260523
    # за реален пример: BoM 580 на dev-teo има 5 ключа в T2, 0 декларации
    # по 45 реда). Тук log-ваме предупреждение, НЕ raise — T2 е optional
    # layer и блокираният save би влошил UX.

    # ── TΠ Availability — public entry за sale_design_configurator ──────
    # Извиква се чрез orm.call от OWL widget на всяка промяна на param
    # (debounced 150ms client-side). Връща normalised dict per param.
    # `@api.model` — context е dict client-side, не record state.

    @api.model
    def _configurator_evaluate_multiplicity(self, bom_id, context):
        """Return TΩ multiplicity metadata за дадения BoM context.

        :param bom_id: int — mrp.bom id.
        :param context: dict — current param values.
        :returns: dict ``{count_param?, per_instance_params?, aggregator?, skip_when?}``
            или празен dict ако TΩ не е дефиниран.
        """
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        table = bom.multiplicity_table
        if not table and bom.matrix_template_id:
            table = bom.matrix_template_id.multiplicity_table
        if not table:
            return {}
        Template = self.env["mrp.matrix.template"]
        from .zen_engine import ZenWrapper
        raw = ZenWrapper.evaluate(table, context or {}, env=self.env)
        return Template._normalize_multiplicity(raw)

    @api.model
    def _configurator_evaluate_cascade(self, bom_id, changed_param, context):
        """Return TΦ cascade state за дадена param промяна.

        :param bom_id: int — mrp.bom id.
        :param changed_param: string — param name (DPD ``string`` field) който се промени.
        :param context: dict — текущи param стойности (design_params).
        :returns: dict ``{target_param: {copy_from?, derive_value?, only_if_empty?}}``.
            ``derive_expression`` от raw rules се resolve-ва тук с safe_eval
            и lookup() helper; клиентът получава already-computed ``derive_value``.
            Празен dict ако TΦ не е дефиниран на BoM-а и template-а.
        """
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        # BoM-копието има приоритет, fallback на template-а. lookup_tables идва
        # от същия owner (BoM ако table-а е override-нат там, иначе template).
        owner = bom if bom.cascade_table else bom.matrix_template_id
        if not owner or not owner.cascade_table:
            return {}
        # Делегираме на template.helper-а ако owner е template (има lookup_tables),
        # иначе ръчно (BoM може да няма lookup_tables — fallback на template).
        Template = self.env["mrp.matrix.template"]
        from .zen_engine import ZenWrapper
        from odoo.tools.safe_eval import safe_eval
        full_context = dict(context or {})
        full_context["changed_param"] = changed_param
        raw = ZenWrapper.evaluate(owner.cascade_table, full_context, env=self.env)
        normalized = Template._normalize_cascade(raw)

        expr_rules = [
            (k, v) for k, v in normalized.items()
            if isinstance(v, dict) and v.get("derive_expression")
        ]
        if not expr_rules:
            return normalized
        # lookup_tables: owner-specific (BoM-override) или fallback template.
        lookup_tables = None
        if bom.cascade_table and hasattr(bom, "lookup_tables") and bom.lookup_tables:
            lookup_tables = bom.lookup_tables
        elif bom.matrix_template_id and bom.matrix_template_id.lookup_tables:
            lookup_tables = bom.matrix_template_id.lookup_tables
        helpers = {
            "lookup": Template._make_lookup(lookup_tables or {}),
            "min": min, "max": max, "abs": abs,
            "int": int, "float": float, "str": str,
            "round": round, "len": len,
        }
        eval_locals = {**full_context, **helpers}
        for target, spec in expr_rules:
            expr = spec.pop("derive_expression")
            try:
                value = safe_eval(expr, eval_locals)
            except Exception as e:
                _logger.warning(
                    "TΦ derive_expression failed за BoM %s target=%s expr=%r: %s",
                    bom.id, target, expr, e,
                )
                continue
            if value is not None and "derive_value" not in spec:
                spec["derive_value"] = value
        return normalized

    @api.model
    def _configurator_evaluate_availability(self, bom_id, context):
        """Return TΠ availability state за дадения BoM и текущ param context.

        :param bom_id: int — mrp.bom id (от dialog props)
        :param context: dict — текущи param стойности (design_params)
        :returns: dict ``{param_name: {visible?, enabled?, allowed_values?,
            default_override?}}``. Празен dict ако TΠ не е дефиниран.
        """
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        # BoM-копието има приоритет; fallback на template-а.
        table = bom.availability_table
        owner = bom
        if not table and bom.matrix_template_id:
            table = bom.matrix_template_id.availability_table
            owner = bom.matrix_template_id
        if not table:
            return {}
        Template = self.env["mrp.matrix.template"]
        # Reuse the normalisation pipeline regardless of owner.
        from .zen_engine import ZenWrapper
        raw = ZenWrapper.evaluate(table, context or {}, env=self.env)
        return Template._normalize_availability(raw)

    @api.constrains(
        "matrix_template_id",
        "material_table",
        "bom_line_ids.matrix_coeff_rule",
    )
    def _check_t2_wiring(self):
        Template = self.env["mrp.matrix.template"]
        for bom in self:
            if not bom.matrix_template_id:
                continue
            # BoM-копието има приоритет над template (потребителят може да е
            # редактирал собственото си копие); fallback на template-а ако е
            # празно.
            table = bom.material_table or bom.matrix_template_id.material_table
            required = Template._extract_t2_coeff_keys(table)
            if not required:
                continue
            declared = {r for r in bom.bom_line_ids.mapped("matrix_coeff_rule") if r}
            missing = sorted(required - declared)
            if missing:
                _logger.warning(
                    "T2 wiring incomplete на BoM %s (id=%s, template=%r): "
                    "material_table иска ключове %s, но никой ред в "
                    "bom_line_ids.matrix_coeff_rule не ги декларира — "
                    "T2 coefficient-ите за тях няма да достигнат до stock moves.",
                    bom.display_name,
                    bom.id,
                    bom.matrix_template_id.name,
                    missing,
                )
