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
import copy
import json
import logging

from odoo import _, api, fields, models
from odoo.addons.base_zen_decision.models.zen_engine import (
    ZenRunner,
    normalize_jdm_graph,
    validate_graph,
)
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import code_translations

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    operation_choice_ids = fields.Many2many(
        "mrp.workcenter",
        "mrp_bom_operation_choice_rel",
        "bom_id",
        "workcenter_id",
        string="Selectable Operations (workcenters)",
        help="Legacy: work centers selectable as operations.",
    )
    # Именувани операции за избор в конфигуратора (различните фрезове и др.):
    # [{"key": "frez_a", "name": "Фреза мотив А", "wc": <workcenter_id>,
    #   "minutes": 20}]. Една машина може да има няколко операции (фрезове).
    operation_choices_def = fields.Json("Selectable Operations")

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
    # Слоевете на конфигуратора (порт от 18.0, фазите A–E). При празно поле
    # се чете таблицата на matrix_template_id.
    cascade_table = fields.Json(
        "TΦ — Cascade Resolutions",
        help=(
            "GoRules JDM. Reactive value propagation rules consumed by the "
            "design configurator. When empty, the table of the matrix "
            "template is used."
        ),
    )
    layout_table = fields.Json(
        "TΛ — Layout / UX Hints",
        help=(
            "GoRules JDM. Declarative UX rules. When empty, the table of the "
            "matrix template is used."
        ),
    )
    multiplicity_table = fields.Json(
        "TΩ — Multiplicity",
        help=(
            "GoRules JDM. Declarative multi-instance metadata. When empty, the "
            "table of the matrix template is used."
        ),
    )
    lookup_tables = fields.Json(
        "Lookup Tables",
        help=(
            "Named lookup tables for TΦ derive_expression rules. When empty, "
            "the tables of the matrix template are used."
        ),
    )
    availability_table = fields.Json(
        "TΠ — Param Availability",
        help=(
            "GoRules JDM. Reactive UI control table consumed by the design "
            "configurator. When empty, the table of the matrix template is "
            "used."
        ),
    )

    _RULE_TABLE_FIELDS = ("constraint_table", "geometry_table",
                          "material_table", "operation_table")
    # Нормализират се при запис, без write-time валидация (виж
    # mrp.matrix.template._CONFIGURATOR_TABLE_FIELDS).
    _CONFIGURATOR_TABLE_FIELDS = ("availability_table", "cascade_table",
                                  "multiplicity_table", "layout_table")

    @api.model
    def _normalize_rule_tables(self, vals):
        """Zero-churn нормализация на легаси „плосък" JDM формат при запис
        (виж mrp.matrix.template._normalize_rule_tables + zen_engine
        normalize_jdm_graph). Тече ПРЕДИ constrains валидацията."""
        for fname in self._RULE_TABLE_FIELDS + self._CONFIGURATOR_TABLE_FIELDS:
            if vals.get(fname):
                vals[fname] = normalize_jdm_graph(vals[fname])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_rule_tables(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_rule_tables(vals)
        return super().write(vals)

    @api.constrains("constraint_table", "geometry_table",
                    "material_table", "operation_table")
    def _check_rule_tables(self):
        """Write-time валидация на T0-T3 графите (D2: доверие).

        Счупен JDM граф (edge към липсващ node, откачена таблица, празни
        rules) досега влизаше ТИХО и се откриваше чак в продукция като
        „таблицата връща [] за всеки контекст" (T3=[] инцидентът) → грешна
        себестойност/липсващи операции без никакъв сигнал. Сега записът се
        отказва с конкретните грешки.
        """
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
                    _("Invalid rule table on BoM %(bom)s:\n- %(problems)s",
                      bom=rec.display_name,
                      problems="\n- ".join(problems)))

    variant_context_map = fields.Json(
        "Variant → Context Map",
        help=(
            "Maps design context keys to product attribute names. "
            "When generating moves, the MO product variant's attribute "
            "values are injected into the design context using this map.\n"
            'Example: {"coating": "Coating"}'
        ),
    )

    # ── Actions ──────────────────────────────────────────────────────────

    def action_load_from_template(self):
        """Копира таблиците на ``matrix_template_id`` в рецептата: T0–T3 и
        слоевете на конфигуратора (TΠ, TΦ, TΩ, TΛ, lookup таблиците)."""
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

    @api.model
    def get_material_choices(self, product_id):
        """Explicit material-choice selectors for the configurator.

        За продукта (вариант на врата) намира BoM-а и връща групи за всеки
        BoM ред с ``material_choice_ids`` (явен списък алтернативи).
        Изборът се пази в design_params под ключ ``choice_<key>`` = product.id
        и заменя placeholder-а на raw move-а при производство.
        """
        product = self.env["product.product"].browse(product_id)
        bom = self.search(
            [
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
                "|",
                ("material_table", "!=", False),
                ("constraint_table", "!=", False),
            ],
            limit=1,
        )
        if not bom:
            return []
        groups = []
        for line in bom.bom_line_ids.filtered(lambda l: l.material_choice_ids):
            key = line.matrix_coeff_rule or ("line%d" % line.id)
            name = (line.material_choice_label
                    or (line.product_id.display_name or "").split(" (")[0])
            groups.append({
                "bomLineId": line.id,
                "choiceKey": "choice_%s" % key,
                "componentName": name,
                "variants": [{
                    "variant_id": p.id,
                    "ptav_name": p.display_name,
                    "imageUrl": "/web/image/product.product/%d/image_128" % p.id,
                } for p in line.material_choice_ids],
            })
        return groups

    @api.model
    def get_operation_choices(self, product_id):
        """Избираеми операции (work centers) за конфигуратора.

        Връща ``operation_choice_ids`` на BoM-а като toggle-и:
        [{wcId, name}]. Изборът се пази в ``stock.lot.matrix_operation_choices``
        (списък wc id) и става work order при производство.
        """
        product = self.env["product.product"].browse(product_id)
        bom = self.search(
            [
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
                "|",
                ("material_table", "!=", False),
                ("constraint_table", "!=", False),
            ],
            limit=1,
        )
        if not bom:
            return []
        defs = bom.operation_choices_def or []
        if defs:
            # sudo: търговецът няма право да чете работните центрове (само
            # групите на Производство), а тук излизат само id и име. Без него
            # изборът на операции ставаше ТИХО празен — JS-ът е в try/catch.
            wc_names = {
                wc.id: wc.name
                for wc in self.env["mrp.workcenter"].sudo().browse(
                    [d.get("wc") for d in defs if d.get("wc")]
                ).exists()
            }
            return [
                {
                    "opKey": d.get("key"),
                    "name": d.get("name"),
                    "wcId": d.get("wc"),
                    "wcName": wc_names.get(d.get("wc")) or "Други",
                }
                for d in defs if d.get("key") and d.get("name")
            ]
        # Fallback: legacy workcenter list.
        return [
            {"opKey": "wc_%d" % wc.id, "name": wc.name,
             "wcId": wc.id, "wcName": wc.name}
            for wc in bom.operation_choice_ids.sudo()
        ]

    @api.model
    def get_component_attributes(self, product_id):
        """Атрибутите на полуфабрикатите (крило/каса/лайсна) за конфигуратора.

        Цветът/материалът се носи от ВЛОЖЕНИТЕ полуфабрикати като
        product.attribute (НЕ от матрицата). Връща за всеки BoM компонент,
        който има color-атрибут (design_role):
        [{componentName, bomLineId, productTmplId, attributes:[{attrId, name,
          isColor, isCoating, isMotif, pairedCoatingAttrId?, values:[{id(ptav),
          valueId, name, seq, html_color?, image?, coating_idx?}]}]}].
        Конфигураторът филтрира цветовете по избраното покритие
        (coating_idx). ``id`` = product.template.attribute.value
        (ptav) — нужно за съставяне на варианта при суап в производството.

        Класификацията идва от product.attribute.design_role (ДАННИ, не код) —
        universal engine-ът не знае индустриални имена; клиентският data модул
        сетва ролите (Solid: loader-ът мигрира по префикс при -u).
        """
        product = self.env["product.product"].browse(product_id)
        bom = self.search(
            [
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
                "|",
                ("material_table", "!=", False),
                ("constraint_table", "!=", False),
            ],
            limit=1,
        )
        if not bom:
            return []
        components = []
        for line in bom.bom_line_ids:
            tmpl = line.product_id.product_tmpl_id
            ptal = tmpl.attribute_line_ids
            roles = ptal.mapped("attribute_id.design_role")
            if "color" not in roles:
                continue
            # pairing: при точно ЕДИН coating атрибут в компонента → двойката е
            # еднозначна и пътува явно; при няколко клиентът пада на своя
            # (клиентски) fallback.
            coating_attrs = ptal.mapped("attribute_id").filtered(
                lambda a: a.design_role == "coating")
            paired_id = coating_attrs.id if len(coating_attrs) == 1 else False
            attrs = []
            for al in ptal:
                attr = al.attribute_id
                is_color = attr.design_role == "color"
                is_coating = attr.design_role == "coating"
                is_motif = attr.design_role == "motif"
                vals = []
                for ptav in al.product_template_value_ids:
                    base = ptav.product_attribute_value_id
                    vd = {
                        "id": ptav.id,
                        "valueId": base.id,
                        "name": base.name,
                        "seq": base.sequence or 0,
                    }
                    if base.html_color:
                        vd["html_color"] = base.html_color
                    if base.image:
                        vd["image"] = (
                            "/web/image/product.attribute.value/%d/image" % base.id
                        )
                    if is_color:
                        vd["coating_idx"] = (base.sequence or 0) // 1000
                    if is_coating:
                        vd["coating_idx"] = base.sequence or 0
                    vals.append(vd)
                attrs.append({
                    "attrId": attr.id,
                    "name": attr.name,
                    "isColor": is_color,
                    "isCoating": is_coating,
                    "isMotif": is_motif,
                    "pairedCoatingAttrId": paired_id if is_color else False,
                    "values": vals,
                })
            components.append({
                "componentName": tmpl.name,
                "bomLineId": line.id,
                "productTmplId": tmpl.id,
                "attributes": attrs,
            })
        return components

    # ── Преводът на съобщенията от правилата ──────────────────────────────

    def _rule_translation_modules(self):
        """Модулите, чиито речници носят текстовете на правилата.

        Съобщенията в T0–T3 са ДАННИ (JSON в таблицата), не низове в код,
        тъй че `.pot` не ги изнася и `env._()` не ги намира: то търси в
        речника на модула, от който е извикано. Затова всеки слой добавя
        себе си тук, а преводът живее в неговия `i18n/<език>.po`, както
        при всички останали текстове.

        Редът е от общото към частното — по-частният речник печели.
        """
        return ["mrp_design_matrix"]

    def _translate_rule_message(self, message):
        """Съобщението на правило на езика на потребителя, ако има превод."""
        text = message if isinstance(message, str) else str(message or "")
        lang = self.env.context.get("lang") or self.env.user.lang
        if not text or not lang or lang.startswith("en"):
            return text
        for module in reversed(self._rule_translation_modules()):
            catalog = code_translations.get_python_translations(module, lang)
            if text in catalog:
                return catalog[text]
        return text

    def _translated_constraint_table(self):
        """Копие на T0 с преведени съобщения — за екрана на поръчката.

        Клиентът оценява таблицата у себе си и показва текста както е в
        нея. Записът в базата остава на английски: един език в данните,
        преводите в речниците.
        """
        self.ensure_one()
        table = self.constraint_table
        if not isinstance(table, dict):
            return table
        table = copy.deepcopy(table)
        for node in table.get("nodes") or []:
            if node.get("type") != "decisionTableNode":
                continue
            outs = [c.get("id") for c in (node.get("content") or {}).get("outputs") or []
                    if c.get("field") == "message" or c.get("id") == "message"]
            for rule in (node.get("content") or {}).get("rules") or []:
                for col in outs:
                    raw = rule.get(col)
                    if isinstance(raw, str) and raw.startswith('"') and raw.endswith('"'):
                        text = json.loads(raw)
                        rule[col] = json.dumps(
                            self._translate_rule_message(text), ensure_ascii=False
                        )
        return table

    # ── Жива симулация на рецептата (цена + разкрой за превю) ─────────────
    # Порт от 18.0. Общ двигател за живия панел на конфигуратора и за
    # автоматичното преизчисляване на MO в клиентските модули: оценява
    # ``quantity_formula`` на всеки ред срещу плоско пространство от
    # дизайн параметрите и връща разбивка за UI, без да създава движения.
    # В 19.0 формулата минава през safe_eval (mode="exec") — същият път, по
    # който mrp_bom_line_formula_template я оценява при производството.

    def _design_eval_namespace(self, design_params_rich, product_uom_qty=1.0):
        """Пространството за ``quantity_formula`` на всеки ред.

        По подразбиране разгъва ``design_params_rich`` (богатия списък от
        ``stock.lot.read(['design_params'])``) по ``name`` И по ``string``,
        добавя ``product_uom_qty`` и съкращенията на размерите
        (``Width (mm)`` → ``width`` и т.н.). Клиентските модули го
        разширяват с изведени променливи.
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
        """Изпълнява ``quantity_formula`` на ред. Връща ``(qty, locals)``,
        за да може извикващият да прочете междинните променливи на
        формулата (``n_pieces``, ``piece_length_mm``, ``pieces``) за
        разкроя. Грешка във формулата дава 0 и запис в лога."""
        if not formula:
            return None, {}
        local = dict(ns)
        try:
            safe_eval(formula, local, mode="exec")
            qty = float(local.get("quantity", local.get("result", 0)) or 0)
            return qty, local
        except Exception as exc:  # noqa: BLE001 — един ред не бива да чупи цената
            _logger.warning(
                "Design formula eval failed on bom %s: %s | expr=%s",
                self.id, exc, (formula or "")[:120],
            )
            return 0.0, local

    @staticmethod
    def _design_formula_uses_dims(formula):
        """Евристика: формулата чете ли размерите на панела? Редовете без
        width/height (капачки, опаковка) се оценяват веднъж, а тези с тях —
        по панел, после се сумират."""
        return ("width" in (formula or "")) or ("height" in (formula or ""))

    @staticmethod
    def _design_normalize_pieces(raw):
        """Разбивката на парчета от формулата — или None, ако я няма.

        Договор (28.08): освен ``n_pieces`` × ``piece_length_mm`` (N еднакви
        парчета) формулата може да присвои ``pieces`` — списък от речници::

            pieces = [{"n": 2, "length_mm": 1150},
                      {"n": 2, "length_mm": 850}]
            pieces = [{"n": 1, "length_mm": 1020, "note": "от руло 140 см"}]

        Двуизмерното парче (``width_mm``) е отказано решение (Влади, 28.08):
        изборът на руло е едномерен, затова ключът не влиза в изхода.

        Формулата е потребителски код: негодното се изхвърля мълчаливо,
        вместо да троши калкулацията. None → извикващият пада на стария
        ``n_pieces``/``piece_length_mm``.
        """
        if not isinstance(raw, (list, tuple)) or not raw:
            return None
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                n = int(item.get("n") or item.get("qty") or 0)
                length = float(item.get("length_mm") or 0)
            except (TypeError, ValueError):
                continue
            if n <= 0 or length <= 0:
                continue
            piece = {"n": n, "length_mm": int(round(length))}
            note = item.get("note")
            if note:
                piece["note"] = str(note)[:64]
            out.append(piece)
        return out or None

    def simulate_with_params(self, design_params_rich, product_uom_qty=1.0,
                             per_subassembly_pairs=None):
        """Оценява формулите на всички редове срещу дадените параметри и
        връща разбивка, готова за UI.

        :param design_params_rich: богатият списък на Properties
            (``stock.lot.read(['design_params'])``)
        :param product_uom_qty: множител на количеството (по подразбиране 1)
        :param per_subassembly_pairs: незадължителен списък ``(width_mm,
            height_mm)`` — по един за повтарящ се подвъзел (напр. две щори в
            една кутия). Формулите с ``width``/``height`` се оценяват по
            панел и се сумират; останалите — веднъж.
        :returns: ``{lines, total_material, active_count, total_count,
            panels}``; всеки ред носи ``bom_line_id``, ``product_id``,
            ``product_name``, ``qty``, ``uom``, ``unit_cost``, ``subtotal``
            и ``cuts`` (разкрой по панел, с ``pieces``, ако формулата ги дава).
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
                        entry = {
                            "panel": idx + 1,
                            "L_mm": int(l_i),
                            "H_mm": int(h_i),
                            "qty_per_panel": float(val),
                            "n_pieces": int(n_pieces) if n_pieces is not None else None,
                            "piece_length_mm": int(piece_len) if piece_len is not None else None,
                        }
                        # Разбивката по парчета е добавка: старите две полета
                        # остават, защото хранят заварените изгледи.
                        pieces = self._design_normalize_pieces(
                            panel_locals.get("pieces"))
                        if pieces:
                            entry["pieces"] = pieces
                        cuts.append(entry)
            else:
                qty, _locals = self._design_eval_formula(formula, base_ns)
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
        """``simulate_with_params`` по шаблон на продукт (активната рецепта)."""
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
        """``simulate_with_params`` по вариант (конфигураторът носи
        product.product, не product.template)."""
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

    # ── Слоевете на конфигуратора: входни точки ───────────────────────────
    # Рецептата има предимство, иначе се чете таблицата на шаблона. Частните
    # методи са за Python; публичните обвивки — за orm.call от OWL, защото
    # Odoo не пуска методи с долна черта през call_kw (в 18.0 TΦ каскадата
    # от конфигуратора тихо падаше точно на това).

    def _configurator_table(self, fname):
        """Таблицата ``fname`` на рецептата или, при празна, на шаблона."""
        self.ensure_one()
        table = self[fname]
        if not table and self.matrix_template_id:
            table = self.matrix_template_id[fname]
        return table

    @api.model
    def _configurator_evaluate_layout(self, bom_id, context=None):
        """TΛ метаданни за рецептата: ``{param: {section?, widget_hint?,
        customer_visible?, submodal?, order?}}`` или празно."""
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        table = bom._configurator_table("layout_table")
        if not table:
            return {}
        raw = ZenRunner.evaluate(table, context or {}, env=self.env)
        return self.env["mrp.matrix.template"]._normalize_layout(raw)

    @api.model
    def _configurator_evaluate_multiplicity(self, bom_id, context):
        """TΩ метаданни за рецептата: ``{count_param?, per_instance_params?,
        aggregator?, skip_when?}`` или празно."""
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        table = bom._configurator_table("multiplicity_table")
        if not table:
            return {}
        raw = ZenRunner.evaluate(table, context or {}, env=self.env)
        return self.env["mrp.matrix.template"]._normalize_multiplicity(raw)

    @api.model
    def _configurator_evaluate_cascade(self, bom_id, changed_param, context):
        """TΦ за промяна на ``changed_param`` (етикетът на параметъра).

        :returns: ``{target_param: {copy_from?, derive_value?, only_if_empty?}}``;
            ``derive_expression`` е изчислен тук с lookup() помощника.
            Lookup таблиците идват от същия притежател: от рецептата, ако
            каскадата е нейна и има свои таблици, иначе от шаблона.
        """
        bom = self.browse(bom_id).exists()
        if not bom:
            return {}
        owner = bom if bom.cascade_table else bom.matrix_template_id
        if not owner or not owner.cascade_table:
            return {}
        Template = self.env["mrp.matrix.template"]
        full_context = dict(context or {})
        full_context["changed_param"] = changed_param
        raw = ZenRunner.evaluate(owner.cascade_table, full_context, env=self.env)
        normalized = Template._normalize_cascade(raw)
        lookup_tables = None
        if bom.cascade_table and bom.lookup_tables:
            lookup_tables = bom.lookup_tables
        elif bom.matrix_template_id and bom.matrix_template_id.lookup_tables:
            lookup_tables = bom.matrix_template_id.lookup_tables
        return Template._resolve_cascade_expressions(
            normalized, full_context, lookup_tables)

    @api.model
    def _configurator_evaluate_availability(self, bom_id, context):
        """TΠ за рецептата и текущия контекст: ``{param: {visible?,
        enabled?, allowed_values?, default_override?}}`` или празно.

        sudo: дилърите в портала и продавачите без производствени права
        нямат четене на mrp.bom — без sudo ограниченията тихо не се
        прилагат. Оценката е само за четене.
        """
        bom = self.sudo().browse(bom_id).exists()
        if not bom:
            return {}
        table = bom._configurator_table("availability_table")
        if not table:
            return {}
        raw = ZenRunner.evaluate(table, context or {}, env=self.env)
        return self.env["mrp.matrix.template"]._normalize_availability(raw)

    @api.model
    def configurator_evaluate_availability(self, bom_id, context):
        """Публична входна точка за TΠ (orm.call от конфигуратора)."""
        return self._configurator_evaluate_availability(bom_id, context)

    @api.model
    def configurator_evaluate_cascade(self, bom_id, changed_param, context):
        """Публична входна точка за TΦ (orm.call от конфигуратора)."""
        return self._configurator_evaluate_cascade(bom_id, changed_param, context)

    @api.model
    def configurator_evaluate_layout(self, bom_id, context=None):
        """Публична входна точка за TΛ (orm.call от конфигуратора)."""
        return self._configurator_evaluate_layout(bom_id, context)

    @api.model
    def configurator_evaluate_multiplicity(self, bom_id, context):
        """Публична входна точка за TΩ (orm.call от конфигуратора)."""
        return self._configurator_evaluate_multiplicity(bom_id, context)

    @api.model
    def configurator_get_bom_meta(self, product_id):
        """Лек sudo поглед за конфигуратора: ``{bom_id, has_availability}``.

        Портален потребител (и продавач без права върху рецептите) не вижда
        mrp.bom — клиентското търсене в диалога връща празно и целият
        клиентски стек на рецептата остава изключен. Тук се дава само
        нужното за TΠ в реално време: id на рецептата и има ли изобщо
        таблица за достъпност (в рецептата или в шаблона).
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
        return {
            "bom_id": bom.id,
            "has_availability": bool(bom._configurator_table("availability_table")),
        }

    @api.model
    def configurator_validate_availability(self, product_id, context):
        """TΠ проверка при потвърждаване (предпазна мрежа до тази в реално
        време). Връща ``[{param, message}]`` — празно значи наред.

        Търси по продукт и със sudo: не иска права върху рецептата и
        работи и когато таблицата е само в шаблона.
        """
        bom = self.sudo().search(
            [
                ("product_tmpl_id.product_variant_ids", "in", [product_id]),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not bom:
            return []
        av = self._configurator_evaluate_availability(bom.id, context or {})
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
            allowed_txt = "/".join(str(a) for a in allowed)
            if param == "main_color" or param.startswith("color_"):
                # един ред за всички цветове — каскадата ги държи заедно
                if color_done:
                    continue
                color_done = True
                msg = self.env._(
                    "The selected colour is not valid for this shutter model "
                    "(e.g. Thermo Comfort is RAL only — no wood texture)."
                )
            elif param == "box_size":
                msg = self.env._(
                    "The box is not valid for this height/axis/slat. Switch "
                    "to box %(allowed)s (recommended: %(recommended)s).",
                    allowed=allowed_txt,
                    recommended=state.get("default_override") or allowed[0],
                )
            elif param == "axis_size":
                msg = self.env._(
                    "This axis is not valid with the selected control — "
                    "allowed axis: %(allowed)s.",
                    allowed=allowed_txt,
                )
            else:
                msg = self.env._(
                    "%(param)s: invalid value. Allowed: %(allowed)s.",
                    param=param,
                    allowed=allowed_txt,
                )
            violations.append({"param": param, "message": msg})
        return violations

    # ── T2: проверка на връзките ──────────────────────────────────────────
    # T2 издава ключове (rope-o, motor-o, …), които редовете трябва да
    # декларират в matrix_coeff_rule; иначе коефициентът отива в нищото.
    # Само предупреждение в лога, не грешка: T2 е незадължителен слой и
    # блокиран запис би влошил работата.

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
            table = bom.material_table or bom.matrix_template_id.material_table
            required = Template._extract_t2_coeff_keys(table)
            if not required:
                continue
            declared = {r for r in bom.bom_line_ids.mapped("matrix_coeff_rule") if r}
            missing = sorted(required - declared)
            if missing:
                _logger.warning(
                    "T2 wiring incomplete on BoM %s (id=%s, template=%r): "
                    "material_table emits keys %s that no line declares in "
                    "matrix_coeff_rule — their T2 coefficients will not reach "
                    "the stock moves.",
                    bom.display_name,
                    bom.id,
                    bom.matrix_template_id.name,
                    missing,
                )
