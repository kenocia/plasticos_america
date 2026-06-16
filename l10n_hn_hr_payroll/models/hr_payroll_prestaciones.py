# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

MESES = {'1': 'Enero',
         '2': 'Febrero',
         '3': 'Marzo',
         '4': 'Abril',
         '5': 'Mayo',
         '6': 'Junio',
         '7': 'Julio',
         '8': 'Agosto',
         '9': 'Septiembre',
         '10': 'Octubre',
         '11': 'Noviembre',
         '12': 'Diciembre'}


class HrPayrollBenefits(models.Model):
    _name = "hr.payroll.benefits"
    _description = "Calculo de las prestaciones"

    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True,
                                  domain="[('active', '=', False)]")
    contract_id = fields.Many2one(related='employee_id.contract_id', string="Contrato", store=True)
    date_hire = fields.Date(related='contract_id.date_start', string='Fecha contratación', required=True)
    date_end = fields.Date(related='employee_id.departure_date', string='Fecha fin del contrato', required=True)
    report_date = fields.Date(string='Fecha de reporte', required=True)
    benefits_ids = fields.One2many('hr.payroll.benefits.months', 'benefits_id', string='Ultimos salarios devengados')

    years_of_service = fields.Integer(related='employee_id.years_of_service', string="Años de antigüedad",
                                      required=True)
    months_of_service = fields.Integer(related='employee_id.months_of_service', string="Meses de antigüedad",
                                       required=True)
    days_of_service = fields.Integer(related='employee_id.days_of_service', string="Días de antigüedad", required=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'Abierto'),
        ('paid', 'Pagado'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')

    total_months = fields.Float(string="Total mensuales", required=True, compute='_total_months', readonly=True,
                                store=True)
    average_month = fields.Float(string="Promedio mensual", required=True, compute='_average_month', readonly=True,
                                 store=True)
    average_daily = fields.Float(string="Promedio Diario", required=True, compute='_average_daily', readonly=True,
                                 store=True)
    average = fields.Float(string="Promedio Mensual Ordinario", required=True, compute='_average', readonly=True,
                           store=True)
    average_ord_daily = fields.Float(string="Promedio Ordinario diario", required=True, compute='_average_ord_daily',
                                     readonly=True,
                                     store=True)
    last_salary = fields.Float(string="Ultimo salario", required=True, compute='_compute_contract_wage', readonly=True,
                               store=True)
    last_salary_daily = fields.Float(string="Ultimo salario diario", required=True, compute='_last_salary_daily',
                                     readonly=True,
                                     store=True)
    total_benefits_duties = fields.Float(string="Total de beneficios y derechos", required=True,
                                         compute='_total_benefits_duties')
    total_benefits = fields.Float(string="Total de beneficios", compute='_total_benefits')

    # Prestaciones
    total_prestaciones = fields.Float(string="Total prestaciones", compute='_total_prestaciones')
    pre_aviso_opt = fields.Selection([
        ('SI', 'SI'),
        ('NO', 'NO'),
    ], index=True, copy=False, default='NO')
    pre_aviso = fields.Integer()
    pre_aviso_amount = fields.Float(compute='_pre_aviso_amount', readonly=True, store=True)

    auxilio_cesantia_opt = fields.Selection([
        ('SI', 'SI'),
        ('NO', 'NO'),
    ], index=True, copy=False, default='NO')
    auxilio_cesantia = fields.Integer()
    auxilio_cesantia_amount = fields.Float(compute='_auxilio_cesantia_amount', readonly=True, store=True)

    auxilio_cesantia_prop = fields.Integer()
    auxilio_cesantia_amount_prop = fields.Float(compute='_auxilio_cesantia_amount_prop', readonly=True, store=True)

    # Derechos
    total_right = fields.Float(string="Total derechos", compute='_total_right')
    holiday_day = fields.Integer()
    holiday_amount = fields.Float(compute='_holiday_amount', readonly=True, store=True)

    holiday_prop = fields.Integer(compute='_holiday_prop', readonly=True, store=True)
    holiday_prop_day = fields.Float()
    holiday_prop_amount = fields.Float(compute='_holiday_prop_amount', readonly=True, store=True)

    val_13avo = fields.Integer()
    val_13avo_day = fields.Float(compute='_val_13avo_day', readonly=True, store=True)
    val_13avo_amount = fields.Float(compute='_val_13avo_amount', readonly=True, store=True)

    val_14avo = fields.Integer()
    val_14avo_day = fields.Float(compute='_val_14avo_day', readonly=True, store=True)
    val_14avo_amount = fields.Float(compute='_val_14avo_amount', readonly=True, store=True)

    pending_salary_day = fields.Integer()
    pending_salary_amount = fields.Float(compute='_pending_salary_amount', readonly=True, store=True)

    pending_overtime = fields.Integer()
    pending_overtime_amount = fields.Float()

    pending_day_off = fields.Integer()
    pending_day_off_amount = fields.Float(compute='_pending_day_off_amount', readonly=True, store=True)

    labor_reserve = fields.Integer()
    labor_reserve_amount = fields.Float(compute='_labor_reserve_amount', readonly=True, store=True)

    # DEDUCCIONES
    total_deduction = fields.Float(string="Total Deducciones", compute='_total_deduction')
    aport_reserve_amount = fields.Float()
    administrative_mistake_amount = fields.Float()
    uniform_amount = fields.Float()

    anticipate_holiday_day = fields.Integer()
    anticipate_holiday_amount = fields.Float(compute='_anticipate_holiday_amount', readonly=True, store=True)

    anticipate_free_day = fields.Integer()
    anticipate_free_amount = fields.Float(compute='_anticipate_free_amount', readonly=True, store=True)

    ipm_amount = fields.Float()

    cobrar_pre_aviso_opt = fields.Selection([
        ('SI', 'SI'),
        ('NO', 'NO'),
    ], index=True, copy=False, default='NO')
    cobrar_pre_aviso_day = fields.Integer()
    cobrar_pre_aviso_amount = fields.Float(compute='_cobrar_pre_aviso_amount', readonly=True, store=True)
    leave_id = fields.Many2one('hr.leave', string="Ausencia")

    @api.constrains('employee_id', 'date_end', 'report_date')
    def _check_benefits_data(self):
        """Validar datos requeridos para el cálculo de prestaciones"""
        for record in self:
            if not record.employee_id:
                raise ValidationError("Debe seleccionar un empleado.")
            if not record.date_end:
                raise ValidationError("Debe especificar la fecha de fin del contrato.")
            if not record.report_date:
                raise ValidationError("Debe especificar la fecha de reporte.")
            if record.date_end < record.contract_id.date_start:
                raise ValidationError("La fecha de fin del contrato no puede ser anterior a la fecha de contratación.")

    def action_period_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_period_open(self):
        self.write({'state': 'open'})
        return True

    def action_refresh(self):
        if self.employee_id:
            self.onchange_employee_id()
        return True

    def action_period_closed(self):
        self.write({'state': 'closed'})
        return True

    @api.depends('employee_id', 'quinquennial_ids.amount_years')
    def _compute_balance(self):
        for record in self:
            total_month = sum(record.benefits_ids.mapped('salary'))
            record.total_months = total_month

    @api.depends('pre_aviso_amount', 'auxilio_cesantia_amount', 'auxilio_cesantia_amount_prop')
    def _total_prestaciones(self):
        for record in self:
            record.total_prestaciones = record.pre_aviso_amount + record.auxilio_cesantia_amount + record.auxilio_cesantia_amount_prop

    @api.depends('holiday_amount', 'holiday_prop_amount', 'val_13avo_amount',
                 'val_14avo_amount', 'pending_salary_amount', 'pending_overtime_amount',
                 'pending_day_off_amount', 'labor_reserve_amount')
    def _total_right(self):
        for record in self:
            record.total_right = (record.holiday_amount + record.holiday_prop_amount + record.val_13avo_amount +
                                  record.val_14avo_amount + record.pending_salary_amount + record.pending_overtime_amount
                                  + record.pending_day_off_amount + record.labor_reserve_amount)

    @api.depends('aport_reserve_amount', 'administrative_mistake_amount', 'uniform_amount',
                 'anticipate_holiday_amount', 'anticipate_free_amount', 'ipm_amount', 'cobrar_pre_aviso_amount')
    def _total_deduction(self):
        for record in self:
            record.total_deduction = (record.aport_reserve_amount + record.administrative_mistake_amount +
                                      record.uniform_amount + record.anticipate_holiday_amount
                                      + record.anticipate_free_amount + record.ipm_amount + record.cobrar_pre_aviso_amount)

    @api.depends('holiday_day', 'average_ord_daily')
    def _holiday_amount(self):
        for record in self:
            record.holiday_amount = record.holiday_day * record.average_ord_daily

    @api.depends('total_prestaciones', 'total_right')
    def _total_benefits_duties(self):
        for record in self:
            record.total_benefits_duties = record.total_prestaciones + record.total_right

    @api.depends('total_benefits_duties', 'total_right')
    def _total_benefits(self):
        for record in self:
            record.total_benefits = record.total_benefits_duties - record.total_deduction

    @api.depends('months_of_service', 'days_of_service')
    def _holiday_prop(self):
        for record in self:
            record.holiday_prop = record.months_of_service * 30 + record.days_of_service

    @api.depends('holiday_prop_day')
    def _holiday_prop_amount(self):
        for record in self:
            record.holiday_prop_amount = record.holiday_prop_day * record.average_ord_daily

    @api.depends('average_ord_daily', 'pre_aviso')
    def _pre_aviso_amount(self):
        for record in self:
            record.pre_aviso_amount = record.average_ord_daily * record.pre_aviso

    @api.depends('average_ord_daily', 'auxilio_cesantia')
    def _auxilio_cesantia_amount(self):
        for record in self:
            record.auxilio_cesantia_amount = record.average_ord_daily * record.auxilio_cesantia

    @api.depends('average_ord_daily', 'auxilio_cesantia_prop')
    def _auxilio_cesantia_amount_prop(self):
        for record in self:
            record.auxilio_cesantia_amount_prop = record.average_ord_daily * record.auxilio_cesantia_prop

    @api.depends('val_13avo', 'average_daily')
    def _val_13avo_day(self):
        for record in self:
            record.val_13avo_day = record.val_13avo / 12 if record.val_13avo else 0

    @api.depends('val_13avo_day', 'average_daily')
    def _val_13avo_amount(self):
        for record in self:
            record.val_13avo_amount = record.val_13avo_day * record.average_daily

    @api.depends('val_14avo', 'average_daily')
    def _val_14avo_day(self):
        for record in self:
            record.val_14avo_day = record.val_14avo / 12 if record.val_14avo else 0

    @api.depends('val_14avo_day', 'average_daily')
    def _val_14avo_amount(self):
        for record in self:
            record.val_14avo_amount = record.val_14avo_day * record.average_daily

    @api.depends('pending_salary_day', 'last_salary_daily')
    def _pending_salary_amount(self):
        for record in self:
            record.pending_salary_amount = record.pending_salary_day * record.last_salary_daily

    @api.depends('pending_day_off', 'last_salary_daily')
    def _pending_day_off_amount(self):
        for record in self:
            record.pending_day_off_amount = record.pending_day_off * record.last_salary_daily

    @api.depends('labor_reserve', 'last_salary_daily')
    def _labor_reserve_amount(self):
        for record in self:
            record.labor_reserve_amount = record.labor_reserve * record.last_salary_daily

    @api.depends('cobrar_pre_aviso_day', 'last_salary_daily')
    def _cobrar_pre_aviso_amount(self):
        for record in self:
            # Falta información
            record.cobrar_pre_aviso_amount = record.cobrar_pre_aviso_day * record.last_salary_daily

    @api.depends('benefits_ids')
    def _total_months(self):
        for record in self:
            record.total_months = 0
            for benefit in record.benefits_ids:
                record.total_months += benefit.salary

    @api.depends('total_months')
    def _average_month(self):
        for record in self:
            if len(record.benefits_ids) > 0:
                record.average_month = record.total_months / len(record.benefits_ids)
            else:
                record.average_month = 0

    @api.depends('average_month')
    def _average_daily(self):
        for record in self:
            record.average_daily = record.average_month / 30 if record.average_month else 0

    @api.depends('average_month')
    def _average(self):
        for record in self:
            # Factor de ajuste para salario ordinario (14/12 = 1.166666...)
            ORDINARY_SALARY_FACTOR = 14.0 / 12.0
            record.average = record.average_month * ORDINARY_SALARY_FACTOR

    @api.depends('average')
    def _average_ord_daily(self):
        for record in self:
            record.average_ord_daily = record.average / 30 if record.average else 0

    def compute_installment(self):
        if not self.employee_id.departure_date:
            return
            
        # Eliminar registros existentes de forma más eficiente
        self.benefits_ids.unlink()
        
        # Calcular fecha límite
        date_to_cal = date(self.employee_id.departure_date.year, self.employee_id.departure_date.month, 1)
        
        # Buscar registros de cierre de nómina
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('contract_id', '=', self.contract_id.id),
            ('date_from', '<', date_to_cal)
        ]
        closing_records = self.env['hr.payroll.closing.table'].search(domain, order='date_to desc', limit=12)
        
        # Crear registros de beneficios de forma masiva
        if closing_records:
            benefits_data = []
            for record in closing_records:
                benefits_data.append({
                    'date_salary_paid': record.date_from,
                    'salary': record.net_salary,
                    'benefits_id': self.id,
                })
            self.env['hr.payroll.benefits.months'].create(benefits_data)
        
        # Calcular días de 13avo y 14avo
        self.val_13avo = self.get_total_day(True)
        self.val_14avo = self.get_total_day(False)

    @api.depends('contract_id')
    def _compute_contract_wage(self):
        for record in self:
            if record.contract_id:
                record.last_salary = record.contract_id.wage

    @api.depends('last_salary')
    def _last_salary_daily(self):
        for record in self:
            record.last_salary_daily = record.last_salary / 30 if record.last_salary else 0

    @api.depends('anticipate_holiday_day', 'last_salary_daily')
    def _anticipate_holiday_amount(self):
        for record in self:
            record.anticipate_holiday_amount = record.last_salary_daily * record.anticipate_holiday_day

    @api.depends('anticipate_free_day', 'last_salary_daily')
    def _anticipate_free_amount(self):
        for record in self:
            record.anticipate_free_amount = record.last_salary_daily * record.anticipate_free_day

    def get_total_day(self, thirteen_avo):
        """Calcula los días totales para 13avo o 14avo"""
        if not self.date_end or not self.contract_id.date_start:
            return 0
            
        days = 0
        try:
            if thirteen_avo:
                # 13avo: desde enero del año actual hasta la fecha de fin
                date_limit = date(self.date_end.year - 1, 12, 1)
                if self.contract_id.date_start > date_limit:
                    return 0
                date_start_cal = date(self.date_end.year, 1, 1)
                diff = relativedelta(self.date_end, date_start_cal)
                days = diff.months * 30 + diff.days + 1
            else:
                # 14avo: desde julio del año anterior hasta la fecha de fin
                date_start_cal = date(self.date_end.year - 1, 7, 1)
                diff = relativedelta(self.date_end, date_start_cal)
                days = diff.months * 30 + diff.days + 1
        except (ValueError, TypeError) as e:
            # Log del error si es necesario
            return 0
            
        return max(0, days)  # Asegurar que no sea negativo
