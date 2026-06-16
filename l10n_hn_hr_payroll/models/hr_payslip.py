# -*- coding:utf-8 -*-

from odoo import fields, models, _, api
from dateutil.relativedelta import relativedelta
from datetime import date

from collections import defaultdict
from datetime import datetime
from odoo.osv import expression


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    leave_allocation_id = fields.Many2one('hr.leave.allocation', string="Petición de asignación")
    overtime_hours_for_all = fields.Boolean("Horas extras")
    sent_to_the_bank = fields.Boolean("Enviado al banco")
    # l10n_hn_worked_days_leaves_count = fields.Integer(
    #     'Worked Days Leaves Count',
    #     compute='_compute_worked_days_leaves_count')

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_hn_hr_payroll', [
                #'data/hr_payroll_structure_data.xml',
                'data/hr_salary_rule_13avo.xml',
                'data/hr_salary_rule_14avo.xml',
                'data/hr_salary_rule_month.xml',
                'data/hr_salary_rule_parameter_data.xml',
                'data/hr_salary_rule_prestaciones.xml',
                'data/hr_salary_rule_quincenal.xml',
            ])]

    def _get_base_local_dict(self):
        res = super()._get_base_local_dict()
        res.update({
            'amount_total_gained_average': amount_total_gained_average,
            'get_total_month': get_total_month,
            'get_total_day': get_total_day,
            'amount_prestaciones': amount_prestaciones,
        })
        return res
    #
    # def _get_worked_day_lines_values(self, domain=None):
    #     self.ensure_one()
    #     res = super()._get_worked_day_lines_values(domain)
    #     if self.struct_id.country_id.code != 'HN':
    #         return res
    #
    #     current_month_domain = expression.AND(
    #         [domain, ['|', ('leave_id', '=', False), ('leave_id.date_from', '>=', self.date_from)]])
    #     res = super()._get_worked_day_lines_values(current_month_domain)
    #
    #     hours_per_day = self._get_worked_day_lines_hours_per_day()
    #     date_from = datetime.combine(self.date_from, datetime.min.time())
    #     date_to = datetime.combine(self.date_to, datetime.max.time())
    #     remainig_work_entries_domain = expression.AND([domain, [('leave_id.date_from', '<', self.date_from)]])
    #     work_entries_dict = self.env
    #     ['hr.work.entry']._read_group(
    #         self.contract_id._get_work_hours_domain(date_from, date_to, domain=remainig_work_entries_domain, inside=True),
    #         ['leave_id', 'work_entry_type_id'],
    #         ['duration:sum'],
    #     )
    #     work_entries = defaultdict(tuple)
    #     work_entries.update({
    #         (work_entry_type.id, leave.id): hours
    #         for leave, work_entry_type, hours in work_entries_dict
    #     })
    #     for work_entry, hours in work_entries.items():
    #         work_entry_id, leave_id = work_entry
    #         work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_id)
    #         days = round(hours / hours_per_day, 5) if hours_per_day else 0
    #         day_rounded = self._round_days(work_entry_type, days)
    #         res.append({
    #             'sequence': work_entry_type.sequence,
    #             'work_entry_type_id': work_entry_id,
    #             'number_of_days': day_rounded,
    #             'number_of_hours': hours,
    #             'l10n_hn_leave_id': leave_id,
    #         })
    #     return res

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        self.ensure_one()
        res = super()._get_worked_day_lines(domain, check_out_of_contract)

        # if self.struct_id.country_id.code != 'HN':
        #     return res

        contract = self.contract_id
        if contract.resource_calendar_id:
            # if not check_out_of_contract:
            #     return res
            out_days, out_hours = 0, 0
            reference_calendar = self._get_out_of_contract_calendar()
            if domain is None:
                domain = [('work_entry_type_id.is_leave', '=', True)]
            else:
                domain = expression.AND([domain, [('work_entry_type_id.is_leave', '=', True)]])
            if self.date_from < contract.date_start:
                start = fields.Datetime.to_datetime(self.date_from)
                stop = fields.Datetime.to_datetime(contract.date_start) + relativedelta(days=-1, hour=23, minute=59)
                out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                out_days += out_time['days']
                out_hours += out_time['hours']
            if contract.date_end and contract.date_end < self.date_to:
                start = fields.Datetime.to_datetime(contract.date_end) + relativedelta(days=1)
                stop = fields.Datetime.to_datetime(self.date_to) + relativedelta(hour=23, minute=59)
                out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                out_days += out_time['days']
                out_hours += out_time['hours']
            if out_days or out_hours:
                work_entry_type = self.env.ref('hr_payroll.hr_work_entry_type_out_of_contract')
                existing = False
                for worked_days in res:
                    if worked_days['work_entry_type_id'] == work_entry_type.id:
                        worked_days['number_of_days'] += out_days
                        worked_days['number_of_hours'] += out_hours
                        existing = True
                        break
                if not existing:
                    res.append({
                        'sequence': work_entry_type.sequence,
                        'work_entry_type_id': work_entry_type.id,
                        'number_of_days': out_days,
                        'number_of_hours': out_hours,
                    })

            leave_otp_ids = []
            for leave in reference_calendar.leave_ids.filtered(lambda l: l.work_entry_type_id.is_leave):
                if (leave.holiday_id and leave.holiday_id.employee_id == self.employee_id and
                        (leave.holiday_id.only_to_pay or leave.holiday_id.holiday_status_id.only_to_pay)):
                    leave_otp_ids.append(leave)

            for line in res:
                if self.env['hr.work.entry.type'].browse(line['work_entry_type_id']).code == "WORK100":
                    for lotp_id in leave_otp_ids:
                        line['number_of_days'] += lotp_id.holiday_id.number_of_days
                        line['number_of_hours'] += lotp_id.holiday_id.number_of_hours

        return res

    def _get_amount_total_gained(self, employee,  date_start_cal, date_to_ca, ruler):
        amount = 0
        domain = [('date_from', '>=', date_start_cal),
                  ('date_to', '<=', date_to_ca),
                  ('employee_id', '=', employee.id)]
        closing_table = self.env['hr.payroll.closing.table'].search(domain)
        for record in closing_table:
            if ruler == 'BASIC':
                amount += record.basic
            if ruler == 'NET':
                amount += record.net_salary
            if ruler == 'GROSS':
                amount += record.gross
        return amount

    def _get_amount_prestaciones(self, employee,  date_start_cal, date_to_ca, ruler):
        amount = 0
        domain = [('report_date', '>=', date_start_cal),
                  ('report_date', '<=', date_to_ca),
                  ('employee_id', '=', employee.id),
                  ('state', '=', 'open'),
                  ]
        closing_table = self.env['hr.payroll.benefits'].search(domain)
        for record in closing_table:
            if ruler == 'TOTAL_MENSUAL':
                amount += record.total_months
            if ruler == 'PROMEDIO_MENSUAL':
                amount += record.average_month
            if ruler == 'PRESTACIONES':
                amount += record.total_prestaciones
            if ruler == 'DERECHOS':
                amount += record.total_right
            if ruler == 'DEDUCCIONES':
                amount += record.total_deduction
            if ruler == 'BENEFICIOS':
                amount += record.total_benefits
        return amount

    def _get_schedule_timedelta(self):
        self.ensure_one()
        schedule = self.contract_id.schedule_pay or self.contract_id.structure_type_id.default_schedule_pay
        if schedule == 'quarterly':
            timedelta = relativedelta(months=3, days=-1)
        elif schedule == 'semi-annually':
            timedelta = relativedelta(months=6, days=-1)
        elif schedule == 'annually':
            timedelta = relativedelta(years=1, days=-1)
        elif schedule == 'weekly':
            timedelta = relativedelta(days=6)
        elif schedule == 'bi-weekly':
            if self.date_from.day > 15:
                if self.date_from.month == 2:
                    if self.date_from.year % 4 == 0:
                        timedelta = relativedelta(days=13)
                    else:
                        if self.date_from.day == 16:
                            timedelta = relativedelta(days=12)
                        else:
                            timedelta = relativedelta(days=14)
                else:
                    if self.date_from.month in (1, 3, 5, 7, 8, 10, 12):
                        timedelta = relativedelta(days=15)
                    else:
                        timedelta = relativedelta(days=14)
            else:
                timedelta = relativedelta(days=14)
        elif schedule == 'semi-monthly':
            timedelta = relativedelta(day=15 if self.date_from.day < 15 else 31)
        elif schedule == 'bi-monthly':
            timedelta = relativedelta(months=2, days=-1)
        elif schedule == 'daily':
            timedelta = relativedelta(days=0)
        else:  # if not handled, put the monthly behaviour
            timedelta = relativedelta(months=1, days=-1)
        return timedelta


def amount_total_gained_average(payslip, employee, thirteen_avo, ruler):
    amount = 0
    if payslip:
        if thirteen_avo:
            date_limit = date(payslip.date_from.year-1, 12, 1)
            if employee.date_hired > date_limit:
                return 0
            date_start_cal = date(payslip.date_from.year-1, 1, 1)
            if employee.date_hired == date_limit:
                date_start_cal = employee.date_hired
            date_to_cal = date(payslip.date_from.year-1, 12, 31)
            amount = payslip._get_amount_total_gained(employee, date_start_cal, date_to_cal, ruler)
        else:
            date_start_cal = date(payslip.date_from.year-1, 7, 1)
            date_to_cal = date(payslip.date_from.year, 6, 30)
            # if employee.date_hired > date_start_cal:
            #     return 0
            # else:
            amount = payslip._get_amount_total_gained(employee, date_start_cal, date_to_cal, ruler)
    return amount


def get_total_month(payslip, employee, thirteen_avo):
    month = 0
    if payslip:
        if thirteen_avo:
            date_limit = date(payslip.date_from.year-1, 12, 1)
            if employee.date_hired > date_limit:
                return 0
            date_start_cal = date(payslip.date_from.year , 1, 1)
            date_to_cal = date(payslip.date_from.year - 1, 12, 31)
            if employee.date_hired <= date_start_cal:
                month = 12
            else:
                diff = relativedelta(date_to_cal, employee.date_hired)
                if diff.months:
                    month = diff.months
        else:
            date_start_cal = date(payslip.date_from.year-1, 7, 1)
            date_to_cal = date(payslip.date_from.year, 6, 30)
            if employee.date_hired <= date_start_cal:
                month = 12
            else:
                diff = relativedelta(date_to_cal, employee.date_hired)
                if diff.months:
                    month = diff.months

    return month


def get_total_day(payslip, employee, thirteen_avo):
    days = 0
    if payslip:
        if thirteen_avo:
            date_limit = date(payslip.date_from.year-1, 12, 1)
            if employee.date_hired > date_limit:
                return 0
            date_start_cal = date(payslip.date_from.year-1 , 1, 1)
            date_to_cal = date(payslip.date_from.year - 1, 12, 31)
            if employee.date_hired <= date_start_cal:
                diff = date_to_cal - date_start_cal
            else:
                diff = date_to_cal - employee.date_hired
            days = diff.days
        else:
            date_start_cal = date(payslip.date_from.year-1, 7, 1)
            date_to_cal = date(payslip.date_from.year, 6, 30)
            if employee.date_hired <= date_start_cal:
                diff = date_to_cal - date_start_cal
            else:
                diff = date_to_cal - employee.date_hired
            days = diff.days
    return days


def amount_prestaciones(payslip, employee, ruler):
    amount = 0
    if payslip:
        amount = payslip._get_amount_prestaciones(employee, payslip.date_from, payslip.date_to, ruler)
    return amount
