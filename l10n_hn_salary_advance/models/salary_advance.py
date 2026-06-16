# -*- coding: utf-8 -*-
import time
from datetime import datetime, date, time
from odoo import fields, models, api, _
from odoo import exceptions
from odoo.exceptions import UserError


class SalaryAdvancePayment(models.Model):
    _name = "salary.advance"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', readonly=True, default=lambda self: 'Adv/')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, help=_("Employee"))
    date = fields.Date(string='Date', required=True, default=lambda self: fields.Date.today(), help=_("Submit date"))
    reason = fields.Text(string='Reason', help="Reason")
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    advance = fields.Float(string='Advance', required=True)
    payment_method = fields.Many2one('account.journal', string='Payment Method')
    exceed_condition = fields.Boolean(string='Exceed than Maximum',
                                      help=_("The Advance is greater than the maximum percentage in salary structure"))
    # department = fields.Many2one('hr.department', string='Department')
    department = fields.Many2one('hr.department', related="employee_id.department_id", readonly=True,
                                    string="Department", help="Employee")
    state = fields.Selection([('draft', _('Draft')),
                              ('submit', _('Submitted')),
                              ('waiting_approval', _('Waiting Approval')),
                              ('approve', _('Approved')),
                              ('process', _('Process')),
                              ('cancel', _('Cancelled')),
                              ('reject', _('Rejected'))], string='Status', default='draft', tracking=True)
    debit = fields.Many2one('account.account', string=_('Debit Account'))
    credit = fields.Many2one('account.account', string=_('Credit Account'))
    journal = fields.Many2one('account.journal', string=_('Journal'))
    employee_contract_id = fields.Many2one('hr.contract', related="employee_id.contract_id", string='Contract')

    advance_thirteen_avo = fields.Boolean(string='Adelanto del 13 Avo',
                                      help=_("Se especifica que el adelanto es el 13 Avo"))

    advance_thirteen_avo_exists = fields.Boolean(compute='_compute_advance_thirteen_exists')

    advance_fourteen_avo = fields.Boolean(string='Adelanto del 14 Avo',
                                      help=_("Se especifica que el adelanto es el 14 Avo"))

    advance_fourteen_avo_exists = fields.Boolean(compute='_compute_advance_fourteen_avo_exists')

    @api.depends('date', 'employee_id')
    def _compute_advance_thirteen_exists(self):
        for salary_advance in self:
            start_date = date(self.date.today().year, 1, 1)
            end_date = date(self.date.today().year, 12, 31)
            salary_advance.advance_thirteen_avo_exists = False
            # Realizar la búsqueda solo si el registro ya tiene un ID (no es nuevo)
            if salary_advance and salary_advance.id and salary_advance.employee_id:
                previous_advances = self.search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('employee_id', '=', salary_advance.employee_id.id),
                    ('advance_thirteen_avo', '=', True),
                    ('state', '=', 'approve'),
                    ('id', '!=', salary_advance.id)  # Excluir el registro actual
                ])
                if previous_advances:
                    salary_advance.advance_thirteen_avo_exists = True

    @api.depends('date', 'employee_id')
    def _compute_advance_fourteen_avo_exists(self):
        for record in self:
            start_date = date(self.date.today().year - 1, 7, 1)
            end_date = date(self.date.today().year, 6, 30)
            record.advance_fourteen_avo_exists = False
            # Realizar la búsqueda solo si el registro ya tiene un ID (no es nuevo)
            if record and record.id and record.employee_id:
                previous_advances = self.search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('employee_id', '=', record.employee_id.id),
                    ('advance_fourteen_avo', '=', True),
                    ('state', '=', 'approve'),
                    ('id', '!=', record.id)  # Excluir el registro actual
                ])
                if previous_advances:
                    record.advance_fourteen_avo_exists = True

    @api.onchange('advance_trece_avo')
    def _onchange_advance_13avo(self):
        if self.advance_thirteen_avo:
            self.advance_fourteen_avo = False

    @api.onchange('advance_14avo')
    def _onchange_advance_14avo(self):
        if self.advance_fourteen_avo:
            self.advance_thirteen_avo = False

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        department_id = self.employee_id.department_id.id
        domain = [('employee_id', '=', self.employee_id.id)]
        return {'value': {'department': department_id}, 'domain': {
            'employee_contract_id': domain,
        }}

    @api.onchange('company_id')
    def onchange_company_id(self):
        company = self.company_id
        domain = [('company_id.id', '=', company.id)]
        result = {
            'domain': {
                'journal': domain,
            },

        }
        return result

    def submit_to_manager(self):
        self.state = 'submit'

    def cancel(self):
        self.state = 'cancel'

    def reject(self):
        self.state = 'reject'

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].get('salary.advance.seq') or ' '
        res_id = super(SalaryAdvancePayment, self).create(vals)
        return res_id

    def approve_request(self):
        """This Approve the employee salary advance request.
                   """
        emp_obj = self.env['hr.employee']
        address = emp_obj.browse([self.employee_id.id]).address_id
        if not address.id:
            raise UserError(_('Define home address for the employee. i.e address under private information of the employee.'))
        salary_advance_search = self.search([('employee_id', '=', self.employee_id.id), ('id', '!=', self.id),
                                             ('state', '=', 'approve')])
        current_month = datetime.strptime(str(self.date), '%Y-%m-%d').date().month
        for each_advance in salary_advance_search:
            existing_month = datetime.strptime(str(each_advance.date), '%Y-%m-%d').date().month
            if current_month == existing_month:
                raise UserError(_('Advance can be requested once in a month'))
        if not self.employee_contract_id:
            raise UserError(_('Define a contract for the employee'))
        if not self.employee_contract_id.structure_type_id:
            raise UserError(_('Define a structure type for the employee'))
        if not self.employee_contract_id.structure_type_id.default_struct_id:
            raise UserError(_('Define a structure for structure type'))
        struct_id = self.employee_contract_id.structure_type_id.default_struct_id
        adv = self.advance
        amt = self.employee_contract_id.wage
        if adv > amt and not self.exceed_condition:
            raise UserError(_('Advance amount is greater than allotted'))

        if not self.advance:
            raise UserError(_('You must Enter the Salary Advance amount'))
        payslip_obj = self.env['hr.payslip'].search([('employee_id', '=', self.employee_id.id),
                                                     ('state', '=', 'done'), ('date_from', '<=', self.date),
                                                     ('date_to', '>=', self.date)])
        if payslip_obj:
            raise UserError(_("This month salary already calculated"))

        for slip in self.env['hr.payslip'].search([('employee_id', '=', self.employee_id.id)]):
            slip_moth = datetime.strptime(str(slip.date_from), '%Y-%m-%d').date().month
            if current_month == slip_moth + 1:
                slip_day = datetime.strptime(str(slip.date_from), '%Y-%m-%d').date().day
                current_day = datetime.strptime(str(self.date), '%Y-%m-%d').date().day
                if current_day - slip_day < struct_id.advance_date:
                    raise exceptions.Warning(
                        _('Request can be done after "%s" Days From prevoius month salary') % struct_id.advance_date)
        self.state = 'waiting_approval'

    def approve_request_acc_dept(self):
        """This Approve the employee salary advance request from accounting department.
                   """
        salary_advance_search = self.search([('employee_id', '=', self.employee_id.id), ('id', '!=', self.id),
                                             ('state', '=', 'approve')])
        current_month = datetime.strptime(str(self.date), '%Y-%m-%d').date().month
        for each_advance in salary_advance_search:
            existing_month = datetime.strptime(str(each_advance.date), '%Y-%m-%d').date().month
            if current_month == existing_month:
                raise UserError(_('Advance can be requested once in a month'))
        if not self.debit or not self.credit or not self.journal:
            raise UserError(_("You must enter Debit & Credit account and journal to approve "))
        if not self.advance:
            raise UserError(_('You must Enter the Salary Advance amount'))

        move_obj = self.env['account.move']
        print('===========================move_obj :',move_obj ,'==============================')
        timenow = datetime.now().strftime('%Y-%m-%d')
        line_ids = []
        debit_sum = 0.0
        credit_sum = 0.0
        for request in self:
            amount = request.advance
            request_name = request.employee_id.name
            reference = request.name
            journal_id = request.journal.id
            move = {
                'narration': 'Salary Advance Of ' + request_name,
                'ref': reference,
                'journal_id': journal_id,
                'date': timenow,
            }

            debit_account_id = request.debit.id
            credit_account_id = request.credit.id

            if debit_account_id:
                debit_line = (0, 0, {
                    'name': request_name,
                    'account_id': debit_account_id,
                    'journal_id': journal_id,
                    'date': timenow,
                    'debit': amount > 0.0 and amount or 0.0,
                    'credit': amount < 0.0 and -amount or 0.0,
                })
                line_ids.append(debit_line)
                debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

            if credit_account_id:
                credit_line = (0, 0, {
                    'name': request_name,
                    'account_id': credit_account_id,
                    'journal_id': journal_id,
                    'date': timenow,
                    'debit': amount < 0.0 and -amount or 0.0,
                    'credit': amount > 0.0 and amount or 0.0,
                })
                line_ids.append(credit_line)
                credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']
            move.update({'line_ids': line_ids})
            draft = move_obj.create(move)
            draft.action_post()
            self.state = 'approve'
            return True
