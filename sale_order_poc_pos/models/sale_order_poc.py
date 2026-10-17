# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
import datetime

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval

# Колко записа най-много се предлагат за избор в касата (many2one/many2many)
L10N_BG_POS_OPTIONS_LIMIT = 80
# Ключът в промените от касата за „Цената тръгва от“ (не е параметър на POC)
L10N_BG_POS_PRICE_BASE_KEY = "__price_base"
# Ключът за опционалните продукти (не е параметър на POC)
L10N_BG_POS_OPTIONAL_KEY = "__optional"
# Ключът за полетата от групите извън параметрите (`_l10n_bg_pos_field_groups`)
L10N_BG_POS_FIELDS_KEY = "__fields"
# Видовете полета, които групите могат да носят
L10N_BG_POS_FIELD_TYPES = ("float", "integer", "boolean")


class SaleOrderPoc(models.Model):
    _inherit = "sale.order.poc"

    def _l10n_bg_pos_data(self):
        """Конфигурацията за тъч редактора на касата (JSON).

        Разделите идват от схемата на шаблона (разделителите) — първо
        основният шаблон, после аспектите; таблиците са само за четене.
        """
        self.ensure_one()
        values = self._poc_values()
        origins = {}
        sections = []
        for container in self._poc_containers():
            origins.update(container.param_origins or {})
            # превключвателят на секцията (sale_order_poc с `section_switch`)
            # отива в заглавието ѝ, не в параметрите
            lines = container.template_id.line_ids
            # изчислените без „може ръчно“ — касата ги показва само за четене
            # (иначе записът гърми в `_poc_mark_manual`)
            locked = {
                line.param_id.code
                for line in lines
                if line.param_id and line.formula and not line.allow_manual
            }
            switches = {
                line.param_id.code
                for line in lines
                if "section_switch" in line._fields and line.section_switch
            }
            current = None
            for entry in container.template_id.param_definition or []:
                if entry["name"] in switches and current is not None:
                    current["switch"] = self._l10n_bg_pos_param(
                        entry, values.get(entry["name"]), origins)
                    continue
                if entry.get("type") == "separator":
                    current = {
                        "title": entry.get("string") or "",
                        "folded": bool(entry.get("fold_by_default")),
                        "params": [],
                    }
                    sections.append(current)
                    continue
                if current is None:
                    current = {
                        "title": container.template_id.display_name,
                        "folded": False,
                        "params": [],
                    }
                    sections.append(current)
                current["params"].append(
                    dict(self._l10n_bg_pos_param(entry, values.get(entry["name"]), origins),
                         readonly=entry["name"] in locked)
                )
        tables = [
            {
                "code": code,
                "rows": [
                    {
                        "key": row["key"],
                        "product": row["product"].display_name if row["product"] else "",
                        "value": row["value"],
                        "uom": row["uom"].name if row["uom"] else "",
                    }
                    for row in rows
                ],
            }
            for code, rows in self._poc_table_values().items()
            if rows
        ]
        so_line = self.sale_line_id
        state_labels = dict(self._fields["state"]._description_selection(self.env))
        # Цената от матрицата (ако е инсталиран sale_order_poc_design_configurator):
        # от какво тръгва и защо я няма — касиерът трябва да го вижда
        price_base = None
        if "matrix_price_base" in self._fields:
            field = self._fields["matrix_price_base"]
            price_base = {
                "value": self.matrix_price_base,
                "label": field._description_string(self.env),
                "options": [
                    {"key": key, "label": label}
                    for key, label in field._description_selection(self.env)
                ],
            }
        price_note = self["matrix_price_note"] if "matrix_price_note" in self._fields else False
        return {
            "companions": self._l10n_bg_pos_companions(),
            "companion_prefix": self._l10n_bg_pos_companion_prefix(),
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": state_labels.get(self.state),
            "editable": self.state == "draft"
            or self.env.user.has_group("sale_order_poc.group_poc_manager"),
            "summary": self.summary or "",
            "sections": [
                section for section in sections if section["params"] or section.get("switch")
            ],
            "optional": self._l10n_bg_pos_optional(),
            "picture": self._l10n_bg_pos_picture() or False,
            "reports": self._l10n_bg_pos_reports(),
            "field_groups": self._l10n_bg_pos_field_groups_data(),
            "tables": tables,
            "price_base": price_base,
            "price_note": price_note or "",
            "line": {
                "id": so_line.id,
                "uuid": so_line.l10n_bg_pos_line_uuid,
                "product": so_line.product_id.display_name,
                "qty": so_line.product_uom_qty,
                "price_unit": so_line.price_unit,
                "discount": so_line.discount,
                "price_subtotal": so_line.price_subtotal,
            },
        }

    def _l10n_bg_pos_picture(self):
        """Картинката до първата секция (видът изделие): ``{"svg": html}``
        или ``{"url": адрес}``, по желание с ``"caption"``.

        Общата рисунка на шаблона (`sale_order_poc_drawing`, О5 — Росен,
        17.10.2026); вертикалът я допълва през `_poc_drawing_fallback` или
        като пренапише тази кука.
        """
        return self._poc_drawing() or False

    def _l10n_bg_pos_picture_preview(self, updates):
        """Картинката с още незаписаните промени от касата — без запис.

        Рисунката на шаблона със стойностите от касата; без нея —
        записаната картинка (куката на вертикала).
        """
        drawing = self._poc_drawing(self._l10n_bg_pos_drawing_values(updates))
        return drawing or self._l10n_bg_pos_picture()

    def _l10n_bg_pos_drawing_values(self, updates):
        """Незаписаните стойности от касата във вида на `_poc_values()`.

        Както в касата на Пакит: числата като float, many2one през browse на
        id-то, селекцията — ключът. Празното е None (рисунката взема
        подразбирането). Кодовете извън схемата и служебните ключове изпадат.
        """
        self.ensure_one()
        types = {}
        comodels = {}
        for container in self._poc_containers():
            for entry in container.template_id.param_definition or []:
                types[entry["name"]] = entry.get("type")
                comodels[entry["name"]] = entry.get("comodel")
        values = {}
        for code, value in (updates or {}).items():
            ptype = types.get(code)
            if not ptype or ptype in ("separator", "table"):
                continue
            if ptype in ("float", "integer"):
                try:
                    values[code] = None if value in (None, False, "") else float(value)
                except (TypeError, ValueError):
                    values[code] = None
            elif ptype in ("many2one", "many2many"):
                comodel = comodels.get(code)
                if not comodel or comodel not in self.env:
                    continue
                ids = value if isinstance(value, list) else [value]
                ids = [i for i in ids if isinstance(i, int) and not isinstance(i, bool)]
                records = self.env[comodel].browse(ids).exists()
                values[code] = records[:1] if ptype == "many2one" else records
            elif ptype == "boolean":
                values[code] = bool(value)
            else:
                values[code] = value if value not in (False, "") else None
        return values

    def _l10n_bg_pos_field_groups(self):
        """Групи полета на POC извън параметрите — кука за вертикала.

        Всяка група е ``{"key", "title", "fields": [имена], "anchor",
        "before"}``: с ``anchor`` (код на параметър) се показва в секцията
        му, точно под него; с ``before`` (код на параметър или на
        превключвател) е своя карта преди секцията му; без двете — карта
        накрая. Полетата са само float, integer и boolean.
        """
        return []

    def _l10n_bg_pos_reports(self):
        """Справки в края на редактора — кука за вертикала.

        ``[{"key", "title", "button"}]``: касата показва картата с бутон и
        вика `_l10n_bg_pos_report(key)` чак при натискането — справката може
        да е бавна (напр. сух пробег на матрицата за всяка клетка).
        """
        return []

    def _l10n_bg_pos_report(self, key):
        """Справката: ``{"columns": [{"label", "numeric"}], "groups":
        [{"title", "rows": [{"cells": [...], "strong": [индекси]}]}],
        "notes": [...]}``. Клетките са вече форматиран текст."""
        raise NotImplementedError(key)

    def _l10n_bg_pos_field_groups_data(self):
        self.ensure_one()
        out = []
        for group in self._l10n_bg_pos_field_groups():
            fields_data = []
            for name in group["fields"]:
                field = self._fields.get(name)
                if not field or field.type not in L10N_BG_POS_FIELD_TYPES:
                    continue
                fields_data.append({
                    "name": name,
                    "label": field._description_string(self.env),
                    "type": field.type,
                    "value": self[name],
                })
            if fields_data:
                out.append({
                    "key": group["key"],
                    "title": group.get("title") or "",
                    "anchor": group.get("anchor") or False,
                    "before": group.get("before") or False,
                    "fields": fields_data,
                })
        return out

    def _l10n_bg_pos_write_fields(self, values):
        """Полетата от групите: само обявените, по вида им."""
        self.ensure_one()
        allowed = {
            name
            for group in self._l10n_bg_pos_field_groups()
            for name in group["fields"]
            if name in self._fields and self._fields[name].type in L10N_BG_POS_FIELD_TYPES
        }
        clean = {}
        for name, value in (values or {}).items():
            if name not in allowed:
                continue
            ftype = self._fields[name].type
            if ftype == "boolean":
                clean[name] = bool(value)
            elif value in (None, False, ""):
                clean[name] = 0
            else:
                try:
                    clean[name] = int(value) if ftype == "integer" else float(value)
                except (TypeError, ValueError):
                    continue
        if clean:
            self.write(clean)

    def _l10n_bg_pos_optional(self):
        """Опционалните продукти на артикула — избраните и възможните."""
        self.ensure_one()
        if "optional_product_ids" not in self._fields:
            return None
        allowed = self.allowed_optional_product_ids
        if not allowed:
            return None
        return {
            "value": self.optional_product_ids.ids,
            "options": [{"id": p.id, "name": p.display_name} for p in allowed],
        }

    def _l10n_bg_pos_companion_prefix(self):
        """Началото на ключа на допълнителните редове на тази конфигурация."""
        self.ensure_one()
        return "poc%d-" % self.id

    def _l10n_bg_pos_companions(self):
        """Допълнителните редове на офертата (сито, дръжки…) — за касата.

        Конфигурацията ги добавя в офертата (`sale_order_poc`,
        `companion_line_ids`), но касата не ги знае: без тях сумата в касата
        е по-малка от офертата. Всеки ред получава постоянен ключ
        ``poc<id>-<ключ>`` в `l10n_bg_pos_line_uuid`: касата го ползва като
        свой uuid, така че запазването на офертата обновява СЪЩИЯ ред, а
        махнатият ред се познава по началото на ключа.
        """
        self.ensure_one()
        if "companion_line_ids" not in self._fields:
            return []
        prefix = self._l10n_bg_pos_companion_prefix()
        out = []
        for line in self.sudo().companion_line_ids:
            uuid = prefix + (line.poc_companion_key or str(line.id))
            if line.l10n_bg_pos_line_uuid != uuid:
                line.l10n_bg_pos_line_uuid = uuid
            out.append({
                "uuid": uuid,
                "product_id": line.product_id.id,
                "product_tmpl_id": line.product_id.product_tmpl_id.id,
                "qty": line.product_uom_qty,
                "price_unit": line.price_unit,
            })
        return out

    def _l10n_bg_pos_param(self, entry, value, origins):
        ptype = entry.get("type")
        param = {
            "code": entry["name"],
            "label": entry.get("string") or entry["name"],
            "type": ptype,
            "suffix": entry.get("suffix") or "",
            "origin": origins.get(entry["name"]) or "",
            "value": self._l10n_bg_pos_jsonify(value, ptype),
        }
        if ptype == "selection":
            # схемата: [[ключ, етикет], …]
            param["options"] = [
                {"key": option[0], "label": option[1]}
                for option in entry.get("selection") or []
            ]
        elif ptype == "tags":
            # схемата: [[ключ, етикет, цвят], …]
            param["options"] = [
                {"key": tag[0], "label": tag[1]} for tag in entry.get("tags") or []
            ]
        elif ptype in ("many2one", "many2many"):
            param["options"] = self._l10n_bg_pos_record_options(entry, value)
        return param

    def _l10n_bg_pos_record_options(self, entry, value):
        comodel = entry.get("comodel")
        if not comodel or comodel not in self.env:
            return []
        try:
            domain = safe_eval(entry.get("domain") or "[]")
        except Exception:  # noqa: BLE001 — непознат домейн: без ограничение
            domain = []
        records = self.env[comodel].search(domain, limit=L10N_BG_POS_OPTIONS_LIMIT)
        if isinstance(value, models.BaseModel):
            records |= value
        return [{"id": record.id, "name": record.display_name} for record in records]

    @staticmethod
    def _l10n_bg_pos_jsonify(value, ptype):
        if isinstance(value, models.BaseModel):
            if ptype == "many2one":
                return value[:1].id or False
            return value.ids
        if isinstance(value, datetime.date):
            return fields.Date.to_string(value)
        return value

    def _l10n_bg_pos_write(self, updates):
        """Стойностите от касата → `_poc_set_params` (единственият писач).

        Кодовете извън схемата се пропускат от писача; тук само превръщаме
        id-тата от касата в записи за many2one/many2many.
        """
        self.ensure_one()
        types = {}
        comodels = {}
        for container in self._poc_containers():
            for entry in container.template_id.param_definition or []:
                types[entry["name"]] = entry.get("type")
                comodels[entry["name"]] = entry.get("comodel")
        clean = {}
        # не е параметър: от какво тръгва цената (sale_order_poc_design_configurator)
        price_base = updates.pop(L10N_BG_POS_PRICE_BASE_KEY, None) if isinstance(updates, dict) else None
        optional = updates.pop(L10N_BG_POS_OPTIONAL_KEY, None) if isinstance(updates, dict) else None
        group_fields = updates.pop(L10N_BG_POS_FIELDS_KEY, None) if isinstance(updates, dict) else None
        if isinstance(group_fields, dict):
            self._l10n_bg_pos_write_fields(group_fields)
        if optional is not None and "optional_product_ids" in self._fields:
            ids = [i for i in optional if isinstance(i, int)]
            self.optional_product_ids = self.allowed_optional_product_ids.filtered(
                lambda p: p.id in ids)
        if price_base and "matrix_price_base" in self._fields:
            keys = [key for key, _label in self._fields["matrix_price_base"]._description_selection(self.env)]
            if price_base in keys:
                self.matrix_price_base = price_base
        for code, value in updates.items():
            ptype = types.get(code)
            if not ptype or ptype in ("separator", "table"):
                continue
            if ptype in ("many2one", "many2many"):
                comodel = comodels.get(code)
                if not comodel or comodel not in self.env:
                    continue
                ids = value if isinstance(value, list) else ([value] if value else [])
                clean[code] = self.env[comodel].browse([i for i in ids if isinstance(i, int)]).exists()
            else:
                clean[code] = value
        if clean:
            self._poc_set_params(clean)
