# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    passage_event_count = fields.Integer(
        compute="_compute_passage_event_count",
        string="Passage Events",
    )

    def _compute_passage_event_count(self):
        # Single grouped count вместо per-record search — мащабируемо
        # при много employees.
        Event = self.env["access.passage.event"].sudo()
        grouped = Event._read_group(
            domain=[("employee_id", "in", self.ids)],
            groupby=["employee_id"],
            aggregates=["__count"],
        )
        counts = {emp.id: cnt for emp, cnt in grouped}
        for emp in self:
            emp.passage_event_count = counts.get(emp.id, 0)

    def action_view_trail_svg(self):
        """Отваря Trail SVG endpoint в нов tab за днешния ден."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/access_control/svg/trail/employee/{self.id}",
            "target": "new",
        }

    def action_view_passage_events(self):
        """Smart button — отваря Passage Trail на този employee:
           - filter: employee_id = self
           - default group: ts:day (за хронологичен trail по дни)
           - default filter: last 7 days (наскоро)
           - sorted по ts (старите → новите вътре в групата)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Passage Trail — %s", self.display_name),
            "res_model": "access.passage.event",
            "view_mode": "list,kanban,graph,pivot,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {
                "search_default_group_ts_day": 1,
                "search_default_filter_week": 1,
                "default_employee_id": self.id,
            },
        }
