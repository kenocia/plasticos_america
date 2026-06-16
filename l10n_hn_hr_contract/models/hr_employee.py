# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import date
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    years_of_service = fields.Integer(string="Años de antigüedad", compute='_compute_years_of_service', store=True)
    months_of_service = fields.Integer(string="Meses de antigüedad", compute='_compute_months_of_service', store=True)
    days_of_service = fields.Integer(string="Días de antigüedad", compute='_compute_days_of_service', store=True)
    previous_days_to_resign = fields.Integer(string="Días previos a solicitar la renuncia",
                                             compute='_get_previous_days_to_resign')
    date_hired = fields.Date(string='Fecha Contratación', help="Fecha de inicio del primer contrato",
                             compute='_compute_date_hired', store=True)
    date_of_stay = fields.Date(string='Fecha Permanencia', help="Fecha de inicio del primer contrato permanente",
                               compute='_compute_date_stay', store=True)

    department_id = fields.Many2one(
        'hr.department',
        readonly=True,
        compute='_compute_department_id',
        store=True,
    )

    job_id = fields.Many2one(
        'hr.job',
        readonly=True,
        compute='_compute_job_id',
        store=True,
    )

    contract_type_id = fields.Many2one(
        'hr.contract.type',
        readonly=True,
        compute='_compute_contract_type_id',
        store=True,
    )

    is_low = fields.Boolean(compute='_compute_is_low', store=True, string="Dado de baja")

    @api.depends('contract_ids', 'contract_ids.state')
    def _compute_is_low(self):
        for employee in self:
            if employee.contract_ids:
                contracts = employee.contract_ids.filtered(lambda c: c.state in ('draft', 'open'))
                if not contracts:
                    employee.is_low = True
                    employee.departure_date = fields.Date.today()
                else:
                    employee.is_low = False

    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.department_id', 'contract_ids.job_id')
    def _compute_department_id(self):
        for employee in self:
            # Se debe modificar y cojer el ultimo contrato
            open_contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
            employee.department_id = open_contract.department_id

    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.department_id', 'contract_ids.job_id')
    def _compute_job_id(self):
        for employee in self:
            # se debe modificar y cojer el ultimo job
            open_contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
            employee.job_id = open_contract.job_id

    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.contract_type_id')
    def _compute_contract_type_id(self):
        for employee in self:
            # se debe modificar y cojer el ultimo job
            open_contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
            employee.contract_type_id = open_contract.contract_type_id
    @api.depends('contract_ids.date_start')
    def _compute_date_hired(self):
        for record in self:
            if record.contract_ids:
                date_hired = min(record.contract_ids.mapped('date_start'))
                record.date_hired = date_hired
            else:
                record.date_hired = 0

    @api.depends('contract_ids.date_start', 'contract_ids.contract_type_id')
    def _compute_date_stay(self):
        domain = [
            ('contract_type_id', '=', self.env.ref('hr.contract_type_permanent').id),
        ]
        for record in self:
            if record.contract_ids:
                domain.append(('employee_id', '=', record.id))
                if record.contract_ids.search(domain):
                    date_of_stay = min(record.contract_ids.search(domain).mapped('date_start'))
                    record.date_of_stay = date_of_stay
                else:
                    record.date_of_stay = 0
            else:
                record.date_of_stay = 0

    @api.depends('contract_ids.date_start')
    def _compute_years_of_service(self):
        for record in self:
            if record.contract_ids:
                date_hired = record.date_hired
                # date_hired = min(record.contract_ids.mapped('date_start'))
                current_date = fields.Date.today()
                if record.departure_date:
                    delta_years = relativedelta(record.departure_date, date_hired).years
                else:
                    delta_years = relativedelta(current_date, date_hired).years
                record.years_of_service = delta_years
            else:
                record.years_of_service = 0

    @api.depends('contract_ids.date_start')
    def _compute_months_of_service(self):
        for record in self:
            if record.contract_ids:
                date_hired = record.date_hired
                # date_hired = min(record.contract_ids.mapped('date_start'))
                current_date = fields.Date.today()
                delta_years = relativedelta(current_date, date_hired).years
                date_hired += relativedelta(years=delta_years)
                if record.departure_date:
                    delta_months = relativedelta(record.departure_date, date_hired).months
                else:
                    delta_months = relativedelta(current_date, date_hired).months
                record.months_of_service = delta_months
            else:
                record.months_of_service = 0

    @api.depends('contract_ids.date_start')
    def _compute_days_of_service(self):
        for record in self:
            if record.contract_ids:
                date_hired = record.date_hired
                # date_hired = min(record.contract_ids.mapped('date_start'))
                current_date = fields.Date.today()
                delta_years = relativedelta(current_date, date_hired).years
                date_hired += relativedelta(years=delta_years)
                if record.departure_date:
                    delta_days = relativedelta(record.departure_date, date_hired).days + 1
                else:
                    delta_days = relativedelta(current_date, date_hired).days + 1
                record.days_of_service = delta_days
            else:
                record.days_of_service = 0

    @api.onchange('contract_ids')
    def _onchange_contract_ids_department_id_job_id(self):
        if self.contract_ids:
            contract = self.contract_ids.filtered(lambda c: c.state == 'open')
            if contract:
                self.department_id = contract.department_id
                self.job_id = contract.job_id
        #     else:
        #         self.department_id = False
        #         self.job_id = False
        # else:
        #     self.department_id = False
        #     self.job_id = False

    def _create_contract_date_arrangement(self, contract):
        contract_dates_updated = []
        date_hired = contract.date_start
        date_init_load = contract.company_id.init_load_vacation_date
        if date_init_load:
            while date_hired + relativedelta(years=1) <= fields.Date.today():
                date_hired += relativedelta(years=1)
                if date_hired > date_init_load:
                    contract_dates_updated.append(date_hired)
        return contract_dates_updated

    @api.depends('years_of_service', 'months_of_service')
    def _get_previous_days_to_resign(self):
        for employee in self:
            month_service_total = employee.years_of_service * 12 + employee.months_of_service
            hr_table_previous_quit_notice = self.env['hr.table.previous.quit.notice'].search([
                ('month_of_service_total_start', '<=', month_service_total),
                ('month_of_service_total_end', '>=', month_service_total)
            ], limit=1)

            if hr_table_previous_quit_notice:
                employee.previous_days_to_resign = hr_table_previous_quit_notice.previous_days
            else:
                employee.previous_days_to_resign = 0

    # def get_previous_days_from_employee(self, employee_id):
    #     return self.previous_days_to_resign

    def get_previous_days_from_employee(self, employee_id):
        employee = self.env['hr.employee'].browse(employee_id)
        return employee.previous_days_to_resign
