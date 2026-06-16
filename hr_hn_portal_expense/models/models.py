# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # is_employee_expense_portal = fields.Boolean('Es empleado de gasto en portal?')
    # portal_user_id = fields.Many2one(
    #     'res.users',
    #     string='Portal User',
    #     domain=lambda self: [('groups_id', 'in', self.env.ref('base.group_portal').id)],
    #     help='Select a portal user.'
    # )


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    def _is_notification_scheduled(self, scheduled_date):
        return scheduled_date





