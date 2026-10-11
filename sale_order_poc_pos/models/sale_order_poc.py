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
            current = None
            for entry in container.template_id.param_definition or []:
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
                    self._l10n_bg_pos_param(entry, values.get(entry["name"]), origins)
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
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": state_labels.get(self.state),
            "editable": self.state == "draft"
            or self.env.user.has_group("sale_order_poc.group_poc_manager"),
            "summary": self.summary or "",
            "sections": [section for section in sections if section["params"]],
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
