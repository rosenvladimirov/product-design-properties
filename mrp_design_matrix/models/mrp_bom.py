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

    _RULE_TABLE_FIELDS = ("constraint_table", "geometry_table",
                          "material_table", "operation_table")

    @api.model
    def _normalize_rule_tables(self, vals):
        """Zero-churn нормализация на легаси „плосък" JDM формат при запис
        (виж mrp.matrix.template._normalize_rule_tables + zen_engine
        normalize_jdm_graph). Тече ПРЕДИ constrains валидацията."""
        for fname in self._RULE_TABLE_FIELDS:
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
            wc_names = {
                wc.id: wc.name
                for wc in self.env["mrp.workcenter"].browse(
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
            for wc in bom.operation_choice_ids
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
