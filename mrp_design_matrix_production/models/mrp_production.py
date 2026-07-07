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
import hashlib
import json
import logging

from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # Конфигурацията (design matrix) живее на MO-то — водещият източник.
    # ``copy=True`` → пътува безплатно през copy_data при split/backorder
    # (core _split_productions ги строи с production.copy_data(...)).
    design_param_definition_id = fields.Many2one(
        "design.param.definition",
        string="Design Parameter Set",
        copy=True,
    )
    design_params = fields.Properties(
        "Design Parameters",
        definition="design_param_definition_id.full_design_params_definition",
        copy=True,
    )

    def _design_producing_lot(self):
        """Произвежданата партида, независимо от версията на Odoo:
        18.0 = ``lot_producing_id`` (единствено), 19.0/20.0 =
        ``lot_producing_ids`` (множество) → прави модула version-agnostic."""
        self.ensure_one()
        if "lot_producing_ids" in self._fields:
            return self.lot_producing_ids[:1]
        return self.lot_producing_id  # Odoo 18

    # ── Design context източник (dual-read: MO пръв, партида fallback) ────
    def _get_design_context(self):
        """Flat design context от конфига на MO-то (същия резолвер като lot).

        Ако произвежданата партида носи configurator избори
        (``matrix_material_choices``), те се вливат отгоре — MO конфигът
        покрива вариантните параметри, изборите остават на партидата.
        """
        self.ensure_one()
        ctx = self.design_param_definition_id._build_context(
            self.design_params, {}
        )
        lot = self._design_producing_lot()
        # matrix_material_choices съществува само на 19.0 lot (18/20 нямат полето)
        # → getattr за version-agnostic модул.
        choices = getattr(lot, "matrix_material_choices", None) if lot else None
        if choices:
            ctx.update(choices)
        return ctx

    def _resolve_design_context(self):
        """MO-first: ако MO носи конфиг → чети него; иначе fallback към
        партидата (engine поведението). Пази PCB/Solid/Teolino работещи
        БЕЗ миграция — те още държат конфига на партидата."""
        self.ensure_one()
        if self.design_param_definition_id:
            return self._get_design_context()
        return super()._resolve_design_context()

    # ── Merge политика: блокирай различен конфиг, пренеси еднаквия ────────
    def _design_config_key(self):
        """Стабилен ключ (definition, params) за сравнение при merge.

        ``design_params`` е Properties proxy — ``dict(...)`` преди сериализация,
        иначе json.dumps сериализира repr-а на обекта (адрес в паметта) →
        всеки запис изглежда различен.
        """
        self.ensure_one()
        return (
            self.design_param_definition_id.id,
            json.dumps(
                dict(self.design_params or {}), sort_keys=True, default=str
            ),
        )

    def _pre_action_split_merge_hook(self, merge=False, split=False):
        res = super()._pre_action_split_merge_hook(merge=merge, split=split)
        if merge and len(self) > 1:
            keys = {p._design_config_key() for p in self}
            if len(keys) > 1:
                raise UserError(
                    _(
                        "Cannot merge manufacturing orders with different "
                        "design configurations. Merge only orders that carry "
                        "the same design parameters — otherwise the produced "
                        "components would be silently mixed."
                    )
                )
        return res

    def action_merge(self):
        # Хук-ът вече гарантира, че всички източници имат ЕДНАКЪВ конфиг →
        # взимаме първия и го пренасяме върху слятото MO (core го строи от
        # нула, без copy).
        src = self[:1]
        action = super().action_merge()
        if (
            src.design_param_definition_id
            and isinstance(action, dict)
            and action.get("res_id")
        ):
            merged = self.browse(action["res_id"])
            merged.write(
                {
                    "design_param_definition_id": src.design_param_definition_id.id,
                    "design_params": src.design_params,
                }
            )
        return action

    # ── Down-propagation към полуфабрикатните child MO-та ────────────────
    def _post_run_manufacture(self, post_production_values):
        res = super()._post_run_manufacture(post_production_values)
        for production in self:
            try:
                production._inherit_design_config_from_parent()
            except Exception as e:  # noqa: BLE001 — best-effort, да не чупи run
                _logger.warning(
                    "Design config down-propagation failed for %s: %s",
                    production.display_name,
                    e,
                )
        return res

    def _inherit_design_config_from_parent(self):
        """Наследи design конфиг от родителското MO при полуфабрикат.

        Child MO (произвежда полуфабрикат) → неговият finished move захранва
        raw move на родителя. Взимаме родителския контекст и извличаме child
        параметрите по ``param_extraction_map`` на свързващия bom.line
        (същата семантика като ``_create_child_lot``), после ги пишем на
        child MO-то. Партидата остава fallback (dual-read), това е за да носи
        и самото MO конфига надолу.
        """
        self.ensure_one()
        if self.design_param_definition_id:
            return  # вече конфигурирано (напр. през procurement values)
        dest = self.move_finished_ids.move_dest_ids[:1]
        if not dest:
            return
        parent = dest.raw_material_production_id[:1]
        bom_line = dest.bom_line_id
        if not (
            parent
            and parent.design_param_definition_id
            and bom_line
            and bom_line.child_definition_id
        ):
            return
        parent_ctx = parent._get_design_context()
        child_params = parent._extract_child_params(bom_line, parent_ctx)
        self.write(
            {
                "design_param_definition_id": bom_line.child_definition_id.id,
                "design_params": child_params or False,
            }
        )

    # ── Контрол на партидата + отпечатък на данните ──────────────────────
    def button_mark_done(self):
        res = super().button_mark_done()
        for mo in self:
            try:
                mo._stamp_design_fingerprint()
            except Exception as e:  # noqa: BLE001 — да не блокира приключването
                _logger.warning(
                    "Design fingerprint stamping failed for %s: %s",
                    mo.display_name,
                    e,
                )
        return res

    def _stamp_design_fingerprint(self):
        """MO = водещ → пиши конфига върху произведената партида и залепи
        човекочетим отпечатък в описанието (``note``) + къс хеш в ``ref``."""
        self.ensure_one()
        if not self.design_param_definition_id:
            return
        lot = self._design_producing_lot()
        if not lot:
            return

        # 1) Партидата поема конфига на MO-то (source of truth).
        # ДЕФИНИЦИЯТА първо и ОТДЕЛНО — Properties валидира ключовете срещу
        # активната дефиниция; ако се пише едновременно със стара/липсваща
        # дефиниция, непознатите ключове се изхвърлят. Присвоява се самият
        # Properties proxy (НЕ dict(...) — той дава дисплей-лейбъли за
        # selection, които са невалидни raw стойности при обратен запис).
        if lot.design_param_definition_id != self.design_param_definition_id:
            lot.design_param_definition_id = self.design_param_definition_id
        if dict(lot.design_params or {}) != dict(self.design_params or {}):
            lot.design_params = self.design_params

        # 2) Отпечатък: четим блок + къс хеш (идемпотентно по ВИДИМ маркер —
        # Html полето санитизира и маха HTML коментари, затова маркерът е
        # видим текст ``df:<hash>``, не коментар).
        block, short = self._design_fingerprint_render()
        note = lot.note or ""
        marker = "df:%s" % short
        if marker not in str(note):
            lot.note = Markup(str(note)) + block
        if not lot.ref:
            lot.ref = short

    def _design_fingerprint_render(self):
        """Върни (html_block, short_hash) на конфига, с който е произведено."""
        self.ensure_one()
        raw = dict(self.design_params or {})
        canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str)
        short = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]

        schema = self.design_param_definition_id.full_design_params_definition or []
        label_by_uuid = {
            p.get("name"): (p.get("string") or p.get("name"))
            for p in schema
            if isinstance(p, dict)
        }
        items = Markup("").join(
            Markup("<li>%s: %s</li>") % (label_by_uuid.get(k, k), v)
            for k, v in raw.items()
        )
        # ``df:<short>`` е ВИДИМ текст (маркер за идемпотентност; Html полето
        # маха коментари, затова не е <!-- -->).
        block = Markup(
            "<p><b>Design fingerprint</b> · df:%s · %s</p><ul>%s</ul>"
        ) % (short, self.name, items)
        return block, short
