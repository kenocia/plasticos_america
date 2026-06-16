# -*- coding:utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import ValidationError
import time
from datetime import datetime, timedelta
from dateutil import relativedelta


class HrPayrollClosingTable(models.Model):
    _name = 'hr.payroll.closing.table'
    _description = 'Tabla Cierre de nómina'
    _rec_name = "employee_id"

    have_payslip = fields.Boolean('Existe Nómina', default=False)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    contract_id = fields.Many2one('hr.contract', 'Contract', required=True)
    date_from = fields.Date(string='Date From', copy=False)
    date_to = fields.Date(string='Date To', copy=False)
    closing_table_details_ids = fields.One2many(
        comodel_name='hr.payroll.closing.table.details',
        inverse_name='closing_table_id',
    )
# Reglas --------------------------------------------------
    basic = fields.Float(string="Salario basico", default=0)
    net_salary = fields.Float(string="Salario neto", default=0)
    bonus = fields.Float(string="Bono", default=0)

# Categorias ----------------------------------------------
    gross = fields.Float(string="Salario devengado", default=0)
# Dias  ----------------------------------------------------
    worked_days = fields.Float(string="Días trabajados", required=True)
    worked_hours = fields.Float(string="Horas trabajadas", required=True)
    overtime = fields.Float(string="Horas extras", default=0)

    @api.depends('closing_table_details_ids')
    def _compute_has_payslip(self):
        for record in self:
            record.payslip = bool(record.closing_table_details_ids)

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_leave(self):
        for closing_table in self:
            if closing_table.date_from and closing_table.date_to and closing_table.employee_id:
                register_leaves = self.search([('date_from', '=', closing_table.date_from),
                                               ('date_to', '=', closing_table.date_to),
                                               ('employee_id', '=', closing_table.employee_id.id)])
                if len(register_leaves) > 1:
                    raise ValidationError(_('No puedes crear dos registro para el trabajador en el mismo periodo de tiempo.'))


class HrPayrollClosingTableDetails(models.Model):
    _name = 'hr.payroll.closing.table.details'
    _description = 'Tabla Cierre de nómina Detalle'
    _rec_name = "employee_id"

    payslip_id = fields.Many2one('hr.payslip')
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True)
    contract_id = fields.Many2one(
        'hr.contract',
        'Contract',
        domain="[('employee_id', '=', employee_id),  ('state', '=', 'open')]",
        required=True)

    date_from = fields.Date(string='Date From', copy=False)
    date_to = fields.Date(string='Date To', copy=False)
    closing_table_id = fields.Many2one('hr.payroll.closing.table', ondelete="cascade")

# Reglas --------------------------------------------------
    basic = fields.Float(string="Salario basico", default=0)
    net_salary = fields.Float(string="Salario neto", default=0)
    bonus = fields.Float(string="Bono", default=0)

# Categorias ----------------------------------------------
    gross = fields.Float(string="Salario devengado", default=0)
# Dias  ----------------------------------------------------
    worked_days = fields.Float(string="Días trabajados", required=True)
    worked_hours = fields.Float(string="Horas trabajadas", required=True)
    overtime = fields.Float(string="Horas extras", default=0)

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_leave(self):
        for closing_table in self:
            if closing_table.date_from and closing_table.date_to and closing_table.employee_id:
                register_leaves = self.search([('date_from', '=', closing_table.date_from),
                                               ('date_to', '=', closing_table.date_to),
                                               ('employee_id', '=', closing_table.employee_id.id)])
                if len(register_leaves) > 1:
                    raise ValidationError(_('No puedes crear dos registro para el trabajador en el mismo periodo de tiempo.'))

    # @api.onchange('employee_id')
    # def _onchange_employee_id(self):
    #     if self.employee_id:
    #         if self.employee_id.contract_ids:
    #         domain = [('employee_id', '=', self.employee_id.id), ('state', '=', 'open')]
    #         return {'domain': {'contract_id': domain}}
    #     else:
    #         return {'domain': {'contract_id': []}}

