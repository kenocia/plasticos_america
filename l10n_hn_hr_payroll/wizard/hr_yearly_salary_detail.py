# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command


class YearlySalaryDetail(models.TransientModel):
    _name = 'yearly.salary.detail'
    _description = 'Hr Salary Employee Detail Report'

    def _get_default_date_from(self):
        year = fields.Date.from_string(fields.Date.today()).strftime('%Y')
        return '{}-01-01'.format(year)

    def _get_default_date_to(self):
        date = fields.Date.from_string(fields.Date.today())
        return date.strftime('%Y') + '-' + date.strftime('%m') + '-' + date.strftime('%d')

    employee_ids = fields.Many2many('hr.employee', 'payroll_emp_rel', 'payroll_id', 'employee_id', string='Employees', required=True, compute='_compute_employee_ids')
    date_from = fields.Date(string='Start Date', required=True, default=_get_default_date_from)
    date_to = fields.Date(string='End Date', required=True, default=_get_default_date_to)
    employee_company_id = fields.Many2one('hr.department', string="Company",
                                          domain=[('level', '=', '0'), ('department_type', '=', 'empresa')])
    employee_branch_ids = fields.Many2many('hr.department', string="Branch", context={'active_test': False},
                                           domain=[('level', '>', '0'), ('department_type', '=', 'sucursal')])
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure')
    is_change_branch = fields.Boolean(string='Is changed Branch', default=False)

    @api.depends('employee_company_id')
    def _compute_employee_ids(self):
        for record in self:
            employee_ids = record.env['hr.employee'].search([])
            if record.employee_company_id:
                employee_ids = employee_ids.filtered(lambda rec: rec.department_id.id == record.employee_company_id.id or rec.department_id in record.employee_company_id.child_ids)
                record.employee_ids = employee_ids if employee_ids else [Command.clear()]
            else:
                record.employee_ids = employee_ids

    @api.onchange('employee_branch_ids')
    def _on_change_employee_branch_ids(self):
        for record in self:
            if not record.is_change_branch:
                if not record.employee_branch_ids:
                    self._compute_employee_ids()
                    continue
                employee_branch_ids = self.env['hr.employee'].search(
                    domain=[('department_id', 'in', record.employee_branch_ids.ids)])
                employee_ids = employee_branch_ids - record.employee_ids
                record.employee_ids = employee_ids if employee_ids else [Command.clear()]
                record.is_change_branch = True

    @api.onchange('employee_company_id')
    def _on_change_employee_company_id(self):
        for record in self:
            record.employee_branch_ids = [Command.clear()]
            record.employee_branch_ids |= record.employee_company_id.child_ids.filtered(
                lambda dt: dt.department_type == 'sucursal')
            record.is_change_branch = True

    def print_report(self):
        """
         To get the date and print the report
         @return: return report
        """
        self.ensure_one()
        data = {'ids': self.env.context.get('active_ids', [])}
        res = self.read()
        res = res and res[0] or {}
        data.update({'form': res})
        return self.env.ref('l10n_hn_hr_payroll.action_report_hryearlysalary').with_context(active_model=self._name).report_action(self, data=data)
