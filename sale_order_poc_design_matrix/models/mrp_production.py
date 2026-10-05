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
"""Матричното MO не се преразгъва по POC след потвърждаване.

ADR solid55-poc-design/0001, т. 6: след потвърждаването истината е дизайн
партидата — матрицата чете от нея, технологът я нормализира и допълва.
Преразгъването от POC (``sale_order_poc_mrp``) пуска стандартната
експлозия на рецептата, без матричния пас: връща изключените редове,
губи варианта, избран по атрибутите в партидата, и количествата от
програмата за листове (Солид, 05.10.2026 — MO/00910 и MO/00914:
стъклопакет 0 → 1, декоративната каса пада на общия артикул, первази
5,9 → 1). Черновата остава: пасът тече при потвърждаване.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    poc_matrix_driven = fields.Boolean(
        compute="_compute_poc_matrix_driven",
        help="The components come from the design lot through the design "
        "matrix; the configuration does not recompute them after "
        "confirmation.",
    )

    @api.depends("state", "bom_id")
    def _compute_poc_matrix_driven(self):
        for production in self:
            production.poc_matrix_driven = production._poc_matrix_driven()

    def _poc_matrix_driven(self):
        """Потвърдено MO, чийто състав е дал матричният пас."""
        self.ensure_one()
        return self.state != "draft" and self._design_matrix_applies()

    def _poc_refresh(self):
        matrix = self.filtered(lambda p: p.poc_id and p._poc_matrix_driven())
        for production in matrix:
            _logger.info(
                "MO %s: configuration changed, components left to the design "
                "matrix (not re-exploded).",
                production.name,
            )
        return super(MrpProduction, self - matrix)._poc_refresh()

    def action_poc_recompute(self):
        matrix = self.filtered(lambda p: p.poc_id and p._poc_matrix_driven())
        if matrix:
            raise UserError(
                self.env._(
                    "%(orders)s: the components come from the design lot through "
                    "the design matrix, not from the configuration. Change the "
                    "design lot to change them.",
                    orders=", ".join(matrix.mapped("name")),
                )
            )
        return super().action_poc_recompute()
