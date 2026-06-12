# -*- coding: utf-8 -*-
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
from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    perimeter_ids = fields.Many2many(
        "access.perimeter",
        relation="hr_department_access_perimeter_rel",
        column1="department_id", column2="perimeter_id",
        string="Default Access Perimeters",
        help="Perimeters that members of this department can access by "
             "default. Auto-populates access.credential.perimeter_ids "
             "when an employee from this department is assigned as the "
             "credential holder.")
