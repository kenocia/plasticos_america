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
    year_of_work = fields.Integer(string="Años de antigüedad", compute='_compute_years_of_work')
    years_of_service = fields.Integer(string="Años de antigüedad", compute='_compute_years_of_service', store=True)
    allowed_vacation_days = fields.Integer(string="Días de vacaciones permitidos anual", readonly=True, compute='_compute_allowed_vacation_days', store=True)
    date_hired = fields.Date(string='Fecha Contratación', help="Fecha de inicio del primer contrato", compute='_compute_date_hired', store=True)
    accumulated_leave_year = fields.Integer(string="Días de vacaciones", readonly=True,
                                            store=True, compute='_compute_accumulated_leave')
    remaining_leave_year = fields.Integer(string="Quedan", readonly=True,
                                          store=True, compute='_compute_accumulated_leave')
    accumulated_leave_month = fields.Integer(string="acumulados mensual", readonly=True,
                                             store=True, compute='_compute_accumulated_leave')
    accumulated_leave_day = fields.Float(string="acumulados dias", readonly=True,
                                         store=True, compute='_compute_accumulated_leave')
    total_vacation_day = fields.Float(string="Total de vacaciones",
                                           readonly=True, compute='_compute_total_vacation_day')
    # frontier_subsidy = fields.Boolean('Subsidio Frontera', default=False)
    permit_vacation_without_acumulated = fields.Boolean('Permitir pedir vacaciones sin acumular', default=False)

    accumulated_leave_day_take = fields.Float(string="Día pedidos sin acumular",
                                         readonly=True, compute='_compute_accumulated_leave_day_take')

    accumulated_day_free = fields.Integer(string="Días libres acumulados",
                                            readonly=True, compute='_compute_accumulated_day_free')
    remaining_day_free = fields.Integer(string="Días Libres Quedan", readonly=True, compute='_compute_accumulated_day_free')

    is_perifoneo = fields.Boolean(related='contract_id.is_perifoneo')
    is_animador = fields.Boolean(related='contract_id.is_animador')

    @api.depends('contract_ids.date_start')
    def _compute_date_hired(self):
        for record in self:
            if record.contract_ids:
                date_hired = min(record.contract_ids.mapped('date_start'))
                record.date_hired = date_hired
            else:
                record.date_hired = 0

    @api.depends('contract_ids.date_start', 'is_perifoneo', 'is_animador')
    def _compute_accumulated_leave_year(self):
        for record in self:
            record.remaining_leave_year = 0
            record.accumulated_leave_year = 0
            vacation_type = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation', raise_if_not_found=False)
            if vacation_type:
                if record.contract_id and (record.contract_id.is_perifoneo or record.contract_id.is_animador):
                    record.remaining_leave_year = 0
                else:
                    allocations = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', record.id),
                        ('state', 'in', ['validate']),
                        ('holiday_status_id', '=', vacation_type.id),
                    ])
                    for allocation in allocations:
                        record.accumulated_leave_year += allocation.number_of_days

                    record.remaining_leave_year = record.accumulated_leave_year

                    leaves = self.env['hr.leave'].search([
                        ('employee_id', '=', record.id),
                        ('state', 'in', ['validate', 'validate1']),
                        ('holiday_status_id', '=', vacation_type.id)])

                    for leave in leaves:
                        record.remaining_leave_year -= leave.number_of_days

    @api.depends('contract_ids.date_start', 'is_perifoneo', 'is_animador')
    def _compute_accumulated_leave(self):
        vacation_type = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation', raise_if_not_found=False)
        for record in self:
            if record.contract_id and (record.contract_id.is_perifoneo or record.contract_id.is_animador):
                record.accumulated_leave_month = 0
                record.accumulated_leave_day = 0
                record.remaining_leave_year = 0
            else:
                record.remaining_leave_year = 0
                record.accumulated_leave_year = 0
                if vacation_type:
                    allocations = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', record.id),
                        ('state', 'in', ['validate']),
                        ('holiday_status_id', '=', vacation_type.id),
                    ])
                    leaves = self.env['hr.leave'].search([
                        ('employee_id', '=', record.id),
                        ('state', 'in', ['validate', 'validate1']),
                        ('holiday_status_id', '=', vacation_type.id)])
                    record.accumulated_leave_year += sum(allocations.mapped('number_of_days')) if allocations else 0
                    days_taken = sum(leaves.mapped('number_of_days')) if leaves else 0
                    record.remaining_leave_year = record.accumulated_leave_year - days_taken
                if record.date_hired:
                    month = record.date_hired.month
                    day = record.date_hired.day
                    is_leap_year = record.date_hired.year % 4 == 0
                    if is_leap_year and month == 2 and day == 29:
                        date_hired_last_year = date(date.today().year - 1, record.date_hired.month, 28)
                    else:
                        date_hired_last_year = date(date.today().year-1, record.date_hired.month, record.date_hired.day)
                    date_hired_this_year = date(date.today().year, record.date_hired.month, record.date_hired.day)
                    db_today = datetime.now().date()
                    if db_today < date_hired_this_year:
                        diff = relativedelta(db_today, date_hired_last_year)
                    else:
                        diff = relativedelta(db_today, date_hired_this_year)
                    diff_months = diff.months
                    diff_days = diff.days
                    per_month = record.allowed_vacation_days / 12
                    per_day = record.allowed_vacation_days / 12/ 30
                    record.accumulated_leave_month = diff_months * per_month
                    record.accumulated_leave_day = diff_days * per_day
                else:
                    record.accumulated_leave_month = 0
                    record.accumulated_leave_day = 0

    @api.depends('contract_ids.date_start', 'is_perifoneo', 'is_animador')
    def _compute_accumulated_leave_day_take(self):
        for record in self:
            record.accumulated_leave_day_take = 0
            if record.contract_id and (record.contract_id.is_perifoneo or record.contract_id.is_animador):
                record.accumulated_leave_day_take = 0
            else:
                if record.date_hired:
                    month = record.date_hired.month
                    day = record.date_hired.day
                    date_hired_this_year = date(date.today().year, record.date_hired.month, record.date_hired.day)
                    db_today = datetime.now().date()
                    is_leap_year = record.date_hired.year % 4 == 0
                    if is_leap_year and month == 2 and day == 29:
                        if db_today < date_hired_this_year:
                            date_init = date(date.today().year - 1, record.date_hired.month,28)
                            date_fin = date_hired_this_year
                        else:
                            date_init = date_hired_this_year
                            date_fin = date(date.today().year + 1, record.date_hired.month,28)
                    else:
                        if db_today < date_hired_this_year:
                            date_init = date(date.today().year-1, record.date_hired.month, record.date_hired.day)
                            date_fin = date_hired_this_year
                        else:
                            date_init = date_hired_this_year
                            date_fin = date(date.today().year + 1, record.date_hired.month, record.date_hired.day)

                    holiday_vacation_anticipate_id = self.env.ref(
                        'l10n_hn_hr_holidays.holiday_status_vacation_anticipate').id
                    day_taken = 0
                    # buscar las vacacionea anticipadas pedidas en ese año
                    leaves = self.env['hr.leave'].search([
                        ('employee_id', '=', record.id),
                        ('state', 'in', ['validate', 'validate1']),
                        ('date_from', '>=', date_init),
                        ('date_to', '<=', date_fin),
                        ('holiday_status_id', '=', holiday_vacation_anticipate_id)])
                    for leave in leaves:
                        day_taken = leave.number_of_days
                    record.accumulated_leave_day_take = day_taken
                else:
                    record.accumulated_leave_day_take = 0

    @api.depends('contract_ids.date_start', 'is_perifoneo', 'is_animador')
    def _compute_total_vacation_day(self):
        for record in self:
            record.total_vacation_day = record.remaining_leave_year + \
                                        record.accumulated_leave_month + \
                                        record.accumulated_leave_day - \
                                        record.accumulated_leave_day_take

    @api.depends('contract_ids.date_start')
    def _compute_years_of_work(self):
        for record in self:
            record._compute_years_of_service()
            record._compute_months_of_service()
            record._compute_days_of_service()
            record._compute_allowed_vacation_days()
            record.year_of_work = record.years_of_service

    @api.depends('contract_ids.date_start')
    def _compute_years_of_service(self):
        for record in self:
            if record.contract_ids:
                date_hired = record.date_hired
                # date_hired = min(record.contract_ids.mapped('date_start'))
                current_date = fields.Date.today()
                delta_years = relativedelta(current_date, date_hired).years
                record.years_of_service = delta_years
            else:
                record.years_of_service = 0

    @api.depends('years_of_service')
    def _compute_allowed_vacation_days(self):
        for rec in self:
            allowed_vacation_days = 0
            # if rec.years_of_service:
            domain = [('years_of_service_start', '<=', rec.years_of_service), ('years_of_service_end', '>=', rec.years_of_service)]
            register = self.env['hr.vacation.quota.table'].search(domain, limit=1)
            if register:
                allowed_vacation_days = register.vacation_days
            rec.allowed_vacation_days = allowed_vacation_days

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

    def compute_years_until_date(self, contract, date_end):
        date_hired = contract.employee_id.date_hired
        current_date = date_end
        delta_years = relativedelta(current_date, date_hired).years
        years_of_service = delta_years
        domain = [('years_of_service_start', '<=', years_of_service),
                  ('years_of_service_end', '>=', years_of_service)]
        register = self.env['hr.vacation.quota.table'].search(domain, limit=1)
        allowed_vacation_days = 0
        if register:
            allowed_vacation_days = register.vacation_days
        if contract.employee_id.accumulated_leave_day_take > 0:
            allowed_vacation_days -= contract.employee_id.accumulated_leave_day_take
        return allowed_vacation_days

    def manage_vacation_assignment_requests(self):
        date_today = fields.Date.from_string(fields.Date.today())
        vacation_type = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation')
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            '|',
            ('date_end', '=', False),
            ('date_end', '=', None),
        ])
        for contract in contracts:
            dates_update = self._create_contract_date_arrangement(contract)
            leave_allocation = self.env['hr.leave.allocation']
            for date_init in dates_update:
                if contract.employee_id.active:
                    days_allocation = self.compute_years_until_date(contract, date_init)
                    if days_allocation > 0:
                        value = {
                            'allocation_type': 'regular',
                            # 'can_approve': True,
                            # 'can_reset': True,
                            'create_uid': 1,
                            'date_from': date_init,
                            'date_to': False,
                            'display_name': 'Asignación de Vacaciones ' + str(days_allocation) + ' días de ' + contract.employee_id.name,
                            'duration_display': 15,
                            'employee_company_id': contract.company_id.id,
                            'employee_id': contract.employee_id.id,
                            # 'employee_ids': contract.employee_id,
                            'holiday_status_id': vacation_type.id,
                            'holiday_type': 'employee',
                            'max_leaves': days_allocation,
                            'number_of_days':  days_allocation,
                            'number_of_days_display': days_allocation,
                            'number_of_hours_display': days_allocation * 8,
                            'private_name': 'vacaciones',
                            'state': 'confirm',
                            'type_request_unit':'day',
                            'validation_type': 'officer',
                        }
                        leave_allocation_element = leave_allocation.search([('holiday_status_id', '=', vacation_type.id),
                                                                          ('employee_id', '=', contract.employee_id.id),
                                                                          ('date_from', '=', date_init)])
                        if not leave_allocation_element:
                            move = leave_allocation.sudo().create(value)

    @api.model
    def manage_vacation_assignment_init_load(self):
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            '|',
            ('date_end', '=', False),
            ('date_end', '=', None),
        ])
        vacation_type = self.env.ref('l10n_hn_hr_holidays.holiday_status_vacation')
        for contract in contracts:
            date_init = contract.company_id.init_load_vacation_date
            if date_init is False:
                raise UserError(_("Debe definir la fecha de carga inicial de las vacaciones"))
            if contract.employee_id.date_hired  and contract.employee_id.date_hired <= date_init:
                if contract.employee_id.active:
                    leave_allocation = self.env['hr.leave.allocation']
                    leave_allocation_element = leave_allocation.search([('holiday_status_id', '=', vacation_type.id),
                                                                        ('employee_id', '=', contract.employee_id.id),
                                                                        ('initial_load', '=', True)])
                    if not leave_allocation_element:
                        value = {
                            'allocation_type': 'regular',
                            # 'can_approve': True,
                            # 'can_reset': True,
                            'initial_load': True,
                            'create_uid': 1,
                            'date_from': date_init,
                            'date_to': False,
                            'display_name': 'Carga inicial de días de vacaciones' + contract.employee_id.name,
                            'duration_display': 15,
                            'employee_company_id': contract.company_id.id,
                            'employee_id': contract.employee_id.id,
                            # 'employee_ids': contract.employee_id,
                            'holiday_status_id': vacation_type.id,
                            'holiday_type': 'employee',
                            'max_leaves': 15,
                            'number_of_days':  15,
                            'number_of_days_display': 15,
                            'number_of_hours_display': 15 * 8,
                            'private_name': 'Carga inicial de vacaciones',
                            'state': 'confirm',
                            'type_request_unit': 'day',
                            'validation_type': 'officer',
                        }
                        move = leave_allocation.sudo().create(value)
        self.send_success_notification()

    def send_success_notification(self):
        message = "La carga inicial de las vacaciones se ha completado con éxito."
        # Enviar la notificación al usuario actual
        self.env['bus.bus']._sendone('notify', self.env.user.partner_id.id, {
            'title': 'Acción Completada',
            'message': message,
            'type': 'success',  # Tipo de notificación para indicar éxito
            'sticky': False,  # Define si la notificación desaparece automáticamente después de cierto tiempo
        })

    @api.depends('contract_ids.date_start', 'is_perifoneo', 'is_animador')
    def _compute_accumulated_day_free(self):
        day_free_type =self.env.ref('l10n_hn_hr_holidays.holiday_status_day_free')
        for record in self:
            record.accumulated_day_free = 0
            record.remaining_day_free = 0
            if record.contract_id and (record.contract_id.is_perifoneo or record.contract_id.is_animador):
                record.accumulated_day_free = 0
                record.remaining_day_free = 0
            else:
                allocations = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', record.id),
                    ('state', 'in', ['validate']),
                    ('holiday_status_id', '=', day_free_type.id),
                ])
                for allocation in allocations:
                    record.accumulated_day_free += allocation.number_of_days

                record.remaining_day_free = record.accumulated_day_free

                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', record.id),
                    ('state', 'in', ['validate', 'validate1']),
                    ('holiday_status_id', '=', day_free_type.id)])

                for leave in leaves:
                    record.remaining_day_free -= leave.number_of_days

