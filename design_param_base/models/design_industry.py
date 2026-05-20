# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

# Пълна нормализация на свободния industry таг → каноничен код.
# Историята: industry беше свободен `Char` на 2 модела с непоследователна
# таксономия (виж diagnosis). Тук смесените оси се сгъват в чист секторен
# речник. Зарежда се ПРИ резолване → 8-те sibling data файла остават
# непокътнати (запазват `industry="bags"`/`"doors"`/…), нулев churn.
INDUSTRY_ALIASES = {
    "base": "base",
    "doors": "doors",
    "roller_garage_door": "doors",
    "bags": "packaging",
    "corrugated": "packaging",
    "food": "food",
    "electronics": "electronics",
}


class DesignIndustry(models.Model):
    """Canonical industry classification for design parameter sets.

    Replaces the former free-text ``industry`` Char on
    ``design.param.definition`` and ``mrp.matrix.template``. Records are
    seeded as data; unknown tags are auto-created on resolution so the
    "new industries by data only" principle is preserved.
    """

    _name = "design.industry"
    _description = "Design Industry"
    _order = "sequence, code"

    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "The industry code must be unique."),
    ]

    @api.model
    def _resolve(self, tag):
        """Resolve a raw industry tag to a canonical ``design.industry``.

        Applies the full-normalization alias map, then get-or-creates the
        canonical record. Empty/falsy tag → empty recordset (no industry).

        :param tag: raw tag string (e.g. ``"bags"``, ``"doors"``).
        :rtype: design.industry recordset (0 or 1 record).
        """
        if not tag or not str(tag).strip():
            return self.browse()
        raw = str(tag).strip().lower()
        canonical = INDUSTRY_ALIASES.get(raw, raw)
        record = self.search([("code", "=", canonical)], limit=1)
        if not record:
            record = self.create(
                {
                    "code": canonical,
                    "name": canonical.replace("_", " ").title(),
                }
            )
        return record
