# Copyright 2024-2026 Rosen Vladimirov  (AGPL-3.0-or-later / commercial)
"""D2 hardening: in-place нормализация на ЗАВАРЕНИТЕ T0-T3 таблици.

Заварени бази (прод rebuild, sibling индустрия модули, v18 порт) могат да
държат легаси „плосък" JDM формат — zen-engine го приема мълчаливо и връща
[] за всеки контекст (T3=[] класа). Write hook-ът нормализира само НОВИ
записи; тук лекуваме съществуващите, за да не може write на съседно поле
да удари constrains върху нелекувана таблица (и за да РАБОТЯТ таблиците).
Идемпотентно: пълен граф се връща непроменен → без write.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

FIELDS = ("constraint_table", "geometry_table",
          "material_table", "operation_table")


def migrate(cr, version):
    if not version:
        return  # fresh install — няма заварени данни
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.base_zen_decision.models.zen_engine import (
        normalize_jdm_graph,
    )
    for model in ("mrp.bom", "mrp.matrix.template"):
        records = env[model].with_context(active_test=False).search(
            ["|" for _ in range(len(FIELDS) - 1)]
            + [(f, "!=", False) for f in FIELDS])
        healed = 0
        for rec in records:
            vals = {}
            for fname in FIELDS:
                raw = rec[fname]
                if not raw:
                    continue
                norm = normalize_jdm_graph(raw)
                if norm is not raw and norm != raw:
                    vals[fname] = norm
            if vals:
                rec.write(vals)
                healed += 1
        if healed:
            _logger.info("D2 migrate: %d %s записа с нормализирани "
                         "легаси таблици.", healed, model)
