# Copyright 2024-2026 Rosen Vladimirov
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
    layout_table = fields.Json(
        "TΛ — Layout / UX Hints",
        help=(
            "GoRules JDM. Declarative UX rules. При празно — fallback на "
            "``matrix_template_id.layout_table``."
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
                "layout_table": t.layout_table,
                "lookup_tables": t.lookup_tables,
            }
        )

    # ── Live BoM simulation (cost + cutting-list preview) ───────────────
    # Generic eval engine used by sale_design_configurator's live preview
    # panel and by downstream auto-recompute hooks on mrp.production.
    # Distinct from the matrix flow (`_generate_design_matrix_moves`):
    # this evaluates each line's `quantity_formula` directly with a flat
    # design-params namespace, returning a breakdown ready for UI rendering
    # without producing any stock.move records.

    # Whitelisted globals for the eval sandbox — data/math primitives only,
    # no I/O or import access.  BoM formulas come from admin-only config so
    # we don't need safe_eval's stricter AST allowlist here (and safe_eval
    # has shown intermittent failures on multi-statement try/except bodies
    # across Odoo builds; plain exec with a primitive globals dict is the
    # tested baseline shared with downstream recompute scripts).
    _DESIGN_FORMULA_GLOBALS = {
        "__builtins__": {
            "int": int, "float": float, "abs": abs, "min": min, "max": max,
            "round": round, "len": len, "sum": sum, "any": any, "all": all,
            "True": True, "False": False, "None": None,
        },
    }

    def _design_eval_namespace(self, design_params_rich, product_uom_qty=1.0):
        """Build the namespace passed to each BoM line's quantity_formula.

        Default behaviour: flatten ``design_params_rich`` (the rich
        properties list as returned by ``stock.lot.read(['design_params'])``)
        into a dict keyed by BOTH the property ``name`` (UUID hash) and its
        human ``string`` label, plus ``product_uom_qty`` and dimension
        shortcuts (``Width (mm)`` → ``width`` etc.).

        Downstream modules can override to add industry-specific derived
        variables (e.g. T1 geometry outputs that would otherwise come from
        the matrix flow's zen evaluation — useful for live preview where
        we don't want to incur the matrix overhead per keystroke).
        """
        self.ensure_one()
        ns = {"product_uom_qty": product_uom_qty}
        label_to_dim = {
            "Width (mm)": "width",
            "Height (mm)": "height",
            "Thickness (mm)": "thickness",
        }
        for prop in (design_params_rich or []):
            if not isinstance(prop, dict):
                continue
            value = prop.get("value")
            if value is None:
                continue
            name = prop.get("name")
            label = prop.get("string") or ""
            if name:
                ns[name] = value
            if label:
                ns[label] = value
                dim_key = label_to_dim.get(label)
                if dim_key:
                    ns[dim_key] = value
        return ns

    def _design_eval_formula(self, formula, ns):
        """Execute a BoM line's quantity_formula in the sandbox.  Returns
        ``(qty: float, locals_after: dict)`` so callers can read out
        intermediate variables the formula set (``n_pieces``,
        ``piece_length_mm``, …) for cutting-list breakdown."""
        if not formula:
            return None, {}
        local = dict(ns)
        try:
            exec(formula, self._DESIGN_FORMULA_GLOBALS, local)
            qty = float(local.get("quantity", local.get("result", 0)) or 0)
            return qty, local
        except Exception as exc:
            _logger.warning(
                "Design formula eval failed on bom %s: %s | expr=%s",
                self.id, exc, (formula or "")[:120],
            )
            return 0.0, local

    @staticmethod
    def _design_formula_uses_dims(formula):
        """Heuristic: does the formula reference panel-specific dimensions?
        Lines that don't use width/height (constants like end-cap counts,
        package count, central-console formulas) eval ONCE; lines that do
        eval per panel and sum (slat, terminal, guide, brush, axis)."""
        return ("width" in (formula or "")) or ("height" in (formula or ""))

    def simulate_with_params(self, design_params_rich, product_uom_qty=1.0,
                             per_subassembly_pairs=None):
        """Evaluate every active BoM line's quantity_formula against the
        given design parameters and return a UI-ready breakdown.

        :param design_params_rich: rich properties list (as returned by
            ``stock.lot.read(['design_params'])``)
        :param product_uom_qty: production qty multiplier (default 1)
        :param per_subassembly_pairs: optional list of ``(width_mm, height_mm)``
            tuples — one per repeated subassembly when a single BoM produces
            N independent panels sharing one assembly (e.g. two-shutter
            roller blinds in one box).  Triggers per-panel evaluation for
            formulas that reference ``width`` / ``height`` and sums the
            per-line quantities; non-dim formulas eval once.
        :returns:
            ``{lines: [...], total_material: float, active_count: int,
               total_count: int, panels: int}``

            Each line carries::

                {
                    "bom_line_id": int,
                    "product_id": int,
                    "product_name": str,
                    "qty": float,                 # total qty for assembly
                    "uom": str,
                    "unit_cost": float,
                    "subtotal": float,
                    "cuts": [                     # per-panel breakdown when
                        {                          # per_subassembly_pairs given
                            "panel": int,         # 1-indexed
                            "L_mm": int,
                            "H_mm": int,
                            "qty_per_panel": float,
                            "n_pieces": int|None, # explicit from formula
                            "piece_length_mm": int|None,
                        },
                        ...
                    ],
                }
        """
        self.ensure_one()
        base_ns = self._design_eval_namespace(design_params_rich, product_uom_qty)
        try:
            sc = int(base_ns.get("shutter_count") or base_ns.get("subassembly_count") or 1)
        except (TypeError, ValueError):
            sc = 1
        pairs = list(per_subassembly_pairs or [])
        use_per_subassembly = bool(pairs) and sc > 1 and len(pairs) >= sc

        out_lines = []
        total_material = 0.0
        active = 0
        for bom_line in self.bom_line_ids:
            formula = (bom_line.quantity_formula or "").strip()
            cuts = []
            if not formula:
                qty = bom_line.product_qty
            elif use_per_subassembly and self._design_formula_uses_dims(formula):
                qty = 0.0
                for idx, (l_i, h_i) in enumerate(pairs[:sc]):
                    panel_ns = dict(base_ns)
                    panel_ns["width"] = l_i
                    panel_ns["height"] = h_i
                    val, panel_locals = self._design_eval_formula(formula, panel_ns)
                    qty += (val or 0.0)
                    if val and val > 0:
                        n_pieces = panel_locals.get("n_pieces")
                        piece_len = panel_locals.get("piece_length_mm")
                        cuts.append({
                            "panel": idx + 1,
                            "L_mm": int(l_i),
                            "H_mm": int(h_i),
                            "qty_per_panel": float(val),
                            "n_pieces": int(n_pieces) if n_pieces is not None else None,
                            "piece_length_mm": int(piece_len) if piece_len is not None else None,
                        })
            else:
                qty, _ = self._design_eval_formula(formula, base_ns)
                if qty is None:
                    qty = bom_line.product_qty
            if qty is None or qty < 0:
                qty = 0.0
            unit_cost = bom_line.product_id.standard_price or 0.0
            subtotal = qty * unit_cost
            total_material += subtotal
            if qty > 0:
                active += 1
            out_lines.append({
                "bom_line_id": bom_line.id,
                "product_id": bom_line.product_id.id,
                "product_name": bom_line.product_id.display_name,
                "qty": qty,
                "uom": bom_line.product_uom_id.name,
                "unit_cost": unit_cost,
                "subtotal": subtotal,
                "cuts": cuts,
            })
        return {
            "lines": out_lines,
            "total_material": total_material,
            "active_count": active,
            "total_count": len(out_lines),
            "panels": (sc if use_per_subassembly else 1),
        }

    @api.model
    def simulate_for_product(self, product_tmpl_id, design_params_rich,
                             product_uom_qty=1.0, per_subassembly_pairs=None):
        """``simulate_with_params`` convenience wrapper that looks up the
        active BoM by ``product_tmpl_id``."""
        bom = self.search(
            [("product_tmpl_id", "=", product_tmpl_id), ("active", "=", True)],
            limit=1,
        )
        if not bom:
            return {
                "lines": [], "total_material": 0.0, "active_count": 0,
                "total_count": 0, "panels": 1,
                "error": "No active BoM for product_tmpl_id %s" % product_tmpl_id,
            }
        return bom.simulate_with_params(
            design_params_rich, product_uom_qty, per_subassembly_pairs,
        )

    @api.model
    def simulate_for_variant(self, product_id, design_params_rich,
                             product_uom_qty=1.0, per_subassembly_pairs=None):
        """``simulate_with_params`` variant-id wrapper for the OWL
        configurator dialog (which carries product.product id, not
        product.template id)."""
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            return {
                "lines": [], "total_material": 0.0, "active_count": 0,
                "total_count": 0, "panels": 1,
                "error": "Product variant %s not found" % product_id,
            }
        return self.simulate_for_product(
            product.product_tmpl_id.id, design_params_rich,
            product_uom_qty, per_subassembly_pairs,
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
    def _configurator_evaluate_layout(self, bom_id, context=None):
        """Return TΛ layout metadata за дадения BoM.

        :param bom_id: int — mrp.bom id.
        :param context: dict (optional) — за условни layout rules.
        :returns: dict ``{param: {section?, widget_hint?, customer_visible?,
            submodal?, order?}}`` или празен dict.
        """
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        table = bom.layout_table
        if not table and bom.matrix_template_id:
            table = bom.matrix_template_id.layout_table
        if not table:
            return {}
        Template = self.env["mrp.matrix.template"]
        from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper
        raw = ZenWrapper.evaluate(table, context or {}, env=self.env)
        return Template._normalize_layout(raw)

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
        from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper
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
        from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper
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
    def configurator_evaluate_availability(self, bom_id, context):
        """Public RPC entry за TΠ availability (дизайнерът го вика по orm.call).

        ``_configurator_evaluate_availability`` е private (долна черта) → Odoo
        блокира private методи в call_kw (``Private methods ... cannot be
        called remotely``), затова orm.call-ът от конфигуратора тихо падаше в
        catch и TΠ enforcement-ът никога не се пускаше. Тоя тънък публичен
        wrapper е стабилната входна точка.
        """
        return self._configurator_evaluate_availability(bom_id, context)

    @api.model
    def configurator_get_bom_meta(self, product_id):
        """Лек sudo lookup за конфигуратора: {bom_id, has_availability}.

        Порталните (share) юзъри нямат read на mrp.bom → клиентският search в
        dialog-а връща празно и целият клиентски BoM стек (таблици/RuleMatrix/
        TΦ cascade) остава изключен — което е желаното (минимална реактивна
        повърхност; пълният стек циклеше дизайнера).  Този метод дава САМО
        каквото трябва за real-time TΠ: bom_id за availability RPC-то + има ли
        изобщо availability таблица (BoM или template fallback).
        """
        bom = self.sudo().search(
            [
                ("product_tmpl_id.product_variant_ids", "in", [product_id]),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not bom:
            return {"bom_id": False, "has_availability": False}
        has_av = bool(
            bom.availability_table
            or (bom.matrix_template_id and bom.matrix_template_id.availability_table)
        )
        return {"bom_id": bom.id, "has_availability": has_av}

    @api.model
    def configurator_validate_availability(self, product_id, context):
        """Confirm-time TΠ валидация (защитна мрежа в допълнение на real-time
        TΠ).  Връща списък нарушения
        ``[{param, message}]`` (празен = ОК) с насоки за корекция.

        Lookup по продукт + sudo → не иска BoM достъп от портален клиент и не
        зависи от напълнена BoM availability_table (fallback към template-а).
        """
        self_sudo = self.sudo()
        bom = self_sudo.search(
            [
                ("product_tmpl_id.product_variant_ids", "in", [product_id]),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not bom:
            return []
        av = self_sudo._configurator_evaluate_availability(bom.id, context or {})
        violations = []
        color_done = False
        for param, state in (av or {}).items():
            if not isinstance(state, dict):
                continue
            allowed = state.get("allowed_values")
            if not isinstance(allowed, list):
                continue
            cur = (context or {}).get(param)
            if cur is None or cur in allowed:
                continue
            is_color = param == "main_color" or param.startswith("color_")
            if is_color:
                if color_done:
                    continue
                color_done = True
                msg = (
                    "Избран цвят не е валиден за този модел щора "
                    "(напр. Thermo Comfort е само RAL — без дървесна текстура)."
                )
            elif param == "box_size":
                msg = (
                    "Кутията не е валидна за тази височина/ос/ламел. "
                    "Минете на кутия %s (препоръчана: %s)."
                    % ("/".join(str(a) for a in allowed),
                       state.get("default_override") or allowed[0])
                )
            elif param == "axis_size":
                msg = (
                    "Тази ос не е валидна с избраното управление — "
                    "позволена ос: %s." % "/".join(str(a) for a in allowed)
                )
            else:
                msg = (
                    "%s: невалидна стойност. Позволени: %s."
                    % (param, "/".join(str(a) for a in allowed))
                )
            violations.append({"param": param, "message": msg})
        return violations

    @api.model
    def _configurator_evaluate_availability(self, bom_id, context):
        """Return TΠ availability state за дадения BoM и текущ param context.

        :param bom_id: int — mrp.bom id (от dialog props)
        :param context: dict — текущи param стойности (design_params)
        :returns: dict ``{param_name: {visible?, enabled?, allowed_values?,
            default_override?}}``. Празен dict ако TΠ не е дефиниран.
        """
        # sudo: дилърите в портала (share юзъри) нямат read достъп до mrp.bom
        # през record rule-ите → без sudo TΠ enforcement-ът гърми с AccessError
        # и ограниченията тихо не се прилагат.  Това е read-only оценка на
        # availability таблицата (същия sudo подход като simulate_with_params).
        self = self.sudo()
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
        from odoo.addons.base_zen_decision.models.zen_engine import ZenWrapper
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
