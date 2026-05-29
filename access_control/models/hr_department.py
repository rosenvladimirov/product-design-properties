# -*- coding: utf-8 -*-
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
