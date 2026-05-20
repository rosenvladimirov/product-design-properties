# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Map the legacy free-text ``industry`` Char to the new ``industry_id``.

Изпълнява се САМО при upgrade на съществуваща база. Старата `industry`
колона остава orphaned след премахването на полето — четем я наживо,
резолваме всяка стойност през design.industry._resolve (alias map +
get-or-create) и попълваме industry_id, после трием старата колона.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'design_param_definition'
          AND column_name = 'industry'
        """
    )
    if not cr.fetchone():
        return  # already migrated / nothing to do

    env = api.Environment(cr, SUPERUSER_ID, {})
    Industry = env["design.industry"].sudo()

    cr.execute(
        """
        SELECT DISTINCT industry
        FROM design_param_definition
        WHERE industry IS NOT NULL AND industry <> ''
        """
    )
    tags = [r[0] for r in cr.fetchall()]
    for tag in tags:
        industry = Industry._resolve(tag)
        if not industry:
            continue
        cr.execute(
            """
            UPDATE design_param_definition
            SET industry_id = %s
            WHERE industry = %s AND industry_id IS NULL
            """,
            (industry.id, tag),
        )
        _logger.info(
            "design.param.definition: industry %r -> design.industry %r (id=%s)",
            tag,
            industry.code,
            industry.id,
        )

    cr.execute("ALTER TABLE design_param_definition DROP COLUMN industry")
    _logger.info("Dropped legacy design_param_definition.industry column")
