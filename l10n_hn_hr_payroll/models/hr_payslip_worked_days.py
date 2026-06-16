# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_hn_leave_id = fields.Many2one('hr.leave', string='Leave', readonly=True)

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'contract_id', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "HN")

        for worked_day in worked_days:
            if worked_day.payslip_id.edited or worked_day.payslip_id.state not in ['draft', 'verify']:
                continue
            if not worked_day.contract_id or worked_day.code == 'OUT' or not worked_day.is_paid or worked_day.is_credit_time:
                worked_days.amount = 0
                continue
            if worked_day.payslip_id.wage_type == "hourly":
                hourly_wage = worked_day.payslip_id.contract_id.hourly_wage
                worked_day.amount = hourly_wage * worked_day.number_of_hours
            else:
                payslip = worked_day.payslip_id
                if worked_day.l10n_hn_leave_id:
                    payslip = self.env['hr.payslip'].search([
                        ('employee_id', '=', worked_day.payslip_id.employee_id.id),
                        ('date_from', '<=', worked_day.l10n_hn_leave_id.date_from),
                        ('date_to', '>=', worked_day.l10n_hn_leave_id.date_from),
                        ('state', 'in', ['done', 'paid']),
                    ], limit=1) or worked_day.payslip_id
                sum_worked_days = worked_day.payslip_id.sum_worked_hours / worked_day.contract_id.resource_calendar_id.hours_per_day
                daily_wage = worked_day.contract_id.contract_wage / (sum_worked_days or 1)
                number_of_days = worked_day.number_of_hours / worked_day.contract_id.resource_calendar_id.hours_per_day
                worked_day.amount = daily_wage * number_of_days

        super(HrPayslipWorkedDays, self - worked_days)._compute_amount()


