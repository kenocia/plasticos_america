# -*- coding:utf-8 -*-
from odoo import _, api, fields, models
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

FREQUENCY_MULTIPLIER_v2 = {'annually': 0.0833333333333333,
                           'semi-annually': 0.1666666666666667,
                           'quarterly': 0.3333333333333333, 'bi-monthly': 0.5,
                           'bi-weekly': 2, 'weekly': 4.33}


class HrContract(models.Model):
    _inherit = 'hr.contract'

    schedule_pay = fields.Selection(string="Pago programado",
                                    related="structure_type_id.default_schedule_pay",
                                    tracking=True)

    # RAP
    apply_rap = fields.Boolean(string="Aplicar RAP", default=False, tracking=True)
    amount_rap = fields.Float(string='Cuota RAP', compute="_compute_rap", tracking=True)
    value_rap = fields.Float(string='Monto RAP en nómina', compute="_compute_rap",
                             tracking=True)
    apply_in_rap = fields.Selection(
        [('first', 'Primera quincena'), ('second', 'Segunda quincena'),
         ('both', 'Ambas quincenas')], string="Aplicar RAP en", tracking=True)
    rap_id = fields.Many2one(string="Parametros RAP", comodel_name="hr.hn.rap",
                             tracking=True, domain=[('state', '=', 'active')])
    # IHSS
    apply_ihss = fields.Boolean(string="Aplicar IHSS", default=False, tracking=True)
    amount_ihss = fields.Float(string='Cuota IHSS', compute="_compute_ihss",
                               tracking=True)
    value_ihss = fields.Float(string='Monto IHSS en nómina', compute="_compute_ihss",
                              tracking=True)
    apply_in_ihss = fields.Selection(
        [('first', 'Primera quincena'), ('second', 'Segunda quincena'),
         ('both', 'Ambas quincenas')], string="Aplicar IHSS en", tracking=True)
    ihss_id = fields.Many2one(string="Parametros IHSS", comodel_name="hr.hn.ihss",
                              tracking=True, domain=[('state', '=', 'active')])
    # ISR
    apply_isr = fields.Boolean(string="Aplicar ISR", default=False, tracking=True)
    amount_isr = fields.Float(string='Cuota ISR', compute='_compute_isr', store=True, tracking=True)
    value_isr = fields.Float(string='Monto ISR en nómina', compute='_compute_isr', store=True, tracking=True)
    apply_in_isr = fields.Selection(
        [('first', 'Primera quincena'), ('second', 'Segunda quincena'),
         ('both', 'Ambas quincenas')], string="Aplicar ISR en", tracking=True)
    isr_id = fields.Many2one(string="Parametros ISR", comodel_name="hr.hn.isr",
                             tracking=True, domain=[('state', '=', 'active')])
    other_income = fields.Float(string="Otros Ingresos", tracking=True, 
                                help="Otros ingresos adicionales para el cálculo del ISR")

    benefit_deduction_ids = fields.One2many(string="Beneficios y deducciones",
                                            comodel_name="hr.hn.benefit.deduction",
                                            inverse_name="contract_id")

    montly_salary = fields.Float(string="Salario mensual",
                                 compute="_compute_montly_salary")
    salary_count = fields.Integer(string="Historial de salarios",
                                  compute="_compute_count")
    ihss_count = fields.Integer(string="Historial de IHSS", compute="_compute_count")
    rap_count = fields.Integer(string="Historial de RAP", compute="_compute_count")
    isr_count = fields.Integer(string="Historial de ISR", compute="_compute_count")
    benefit_deduction_count = fields.Integer(
        string="Historial de Beneficios y dedcucciones", compute="_compute_count")

    def _compute_count(self):
        for contract in self:
            history = self.env['hr.hn.salary.history'].search_count(
                [('contract_id', '=', contract.id),
                 ('employee_id', '=', contract.employee_id.id)])
            contract.salary_count = history
            history = self.env['hr.hn.ihss.history'].search_count(
                [('contract_id', '=', contract.id),
                 ('employee_id', '=', contract.employee_id.id)])
            contract.ihss_count = history
            history = self.env['hr.hn.rap.history'].search_count(
                [('contract_id', '=', contract.id),
                 ('employee_id', '=', contract.employee_id.id)])
            contract.rap_count = history
            history = self.env['hr.hn.isr.history'].search_count(
                [('contract_id', '=', contract.id),
                 ('employee_id', '=', contract.employee_id.id)])
            contract.isr_count = history
            history = self.env['hr.hn.benefit.deduction.history'].search_count(
                [('contract_id', '=', contract.id),
                 ('employee_id', '=', contract.employee_id.id)])
            contract.benefit_deduction_count = history

    @api.depends('apply_rap', 'rap_id', 'montly_salary', 'apply_in_rap', 'schedule_pay')
    def _compute_rap(self):
        for contract in self:
            rap = 0
            rap_periodicity = 0
            if contract.apply_rap and contract.rap_id:
                if contract.montly_salary > contract.rap_id.limit_amount:
                    rap = (
                                      contract.montly_salary - contract.rap_id.limit_amount) * contract.rap_id.percentage_rap
                else:
                    rap = contract.montly_salary * contract.rap_id.percentage_rap

                if contract.apply_in_rap == 'both':
                    rap_periodicity = rap / 2
                else:
                    rap_periodicity = rap

            contract.amount_rap = rap
            contract.value_rap = rap_periodicity

    @api.depends('apply_ihss', 'ihss_id', 'montly_salary', 'apply_in_ihss',
                 'schedule_pay')
    def _compute_ihss(self):
        for contract in self:
            ihss = 0
            ihss_periodicity = 0
            if contract.apply_ihss and contract.ihss_id:
                ihss = contract.ihss_id.fee_ihss
                if contract.apply_in_ihss == 'both':
                    ihss_periodicity = ihss / 2
                else:
                    ihss_periodicity = ihss

            contract.amount_ihss = ihss
            contract.value_ihss = ihss_periodicity

    @api.depends('apply_isr', 'isr_id', 'montly_salary', 'apply_in_isr', 'schedule_pay',
                 'amount_rap', 'amount_ihss', 'other_income')
    def _compute_isr(self):
        """
        Obtiene el ISR desde la línea del reporte ISR (hn.isr.line) si existe,
        o calcula un valor básico si no hay reporte generado.
        """
        for contract in self:
            isr = 0
            isr_periodicity = 0
            
            if not contract.apply_isr or not contract.isr_id:
                contract.amount_isr = 0
                contract.value_isr = 0
                continue
            
            # Buscar la línea ISR correspondiente a este contrato
            isr_line = self.env['hn.isr.line'].search([
                ('contract_id', '=', contract.id),
                ('parent_id', '=', contract.isr_id.id)
            ], limit=1)
            
            if isr_line:
                # Usar el valor ya calculado del reporte ISR
                isr = isr_line.isr_fee
                _logger.info(f"✓ ISR tomado del reporte para {contract.employee_id.name}: {isr:,.2f}")
            else:
                # Si no hay línea ISR, calcular un valor básico
                if contract.montly_salary > contract.isr_id.exempt_salary:
                    # Cálculo básico sin otros ingresos
                    total_incomes = contract.montly_salary * 12
                    amount_rap = contract.amount_rap * 12
                    amount_ivm = contract.ihss_id.fee_ivm * 12 if contract.ihss_id else 0
                    total_base = total_incomes - amount_rap - amount_ivm
                    
                    # Cálculo simplificado del ISR
                    ranges = contract.isr_id.range_ids.sorted('amount_from')
                    retention_total = 0
                    
                    for range_rec in ranges:
                        if range_rec.rate > 0 and total_base > range_rec.amount_from:
                            if total_base <= range_rec.amount_to or range_rec.amount_to == 0:
                                amount_in_range = total_base - range_rec.amount_from
                            else:
                                amount_in_range = range_rec.amount_to - range_rec.amount_from
                            
                            if range_rec.rate < 1:
                                isr_rango = amount_in_range * range_rec.rate
                            else:
                                isr_rango = amount_in_range * range_rec.rate / 100
                            
                            retention_total += isr_rango
                    
                    isr = retention_total / 12
                    _logger.info(f"✓ ISR calculado básico para {contract.employee_id.name}: {isr:,.2f}")
                else:
                    isr = 0
                    _logger.info(f"✓ Salario exento para {contract.employee_id.name}")
            
            # Calcular ISR por periodo según la periodicidad
            if contract.apply_in_isr == 'both':
                isr_periodicity = isr / 2
            else:
                isr_periodicity = isr
            
            contract.amount_isr = isr
            contract.value_isr = isr_periodicity
    
    def action_recalculate_isr(self):
        """Botón para forzar recálculo del ISR y mostrar mensaje"""
        self.ensure_one()
        
        if not self.apply_isr or not self.isr_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Advertencia'),
                    'message': _('Debe activar ISR y seleccionar una configuración ISR primero.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Buscar la línea ISR correspondiente
        isr_line = self.env['hn.isr.line'].search([
            ('contract_id', '=', self.id),
            ('parent_id', '=', self.isr_id.id)
        ], limit=1)
        
        # Forzar recálculo
        self._compute_isr()
        
        if isr_line:
            source_info = f"""
            <tr style="background: #e8f5e8;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>📊 Fuente:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;"><b>Reporte ISR Generado</b></td>
            </tr>
            <tr style="background: #e8f5e8;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Total Base Imponible (Reporte):</b></td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{isr_line.total_base:,.2f}</td>
            </tr>
            <tr style="background: #e8f5e8;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Otros Ingresos (Reporte):</b></td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{isr_line.other_income:,.2f}</td>
            </tr>
            """
        else:
            source_info = f"""
            <tr style="background: #fff3cd;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>⚠️ Fuente:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;"><b>Cálculo Básico (Sin Reporte)</b></td>
            </tr>
            <tr style="background: #fff3cd;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>💡 Recomendación:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;"><b>Genere el Reporte ISR</b></td>
            </tr>
            """
        
        message = f"""
        <div style="font-family: monospace;">
            <h3>✓ ISR Sincronizado para {self.employee_id.name}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f0f0f0;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Salario Mensual:</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{self.montly_salary:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Salario Anual:</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{self.montly_salary * 12:,.2f}</td>
                </tr>
                <tr style="background: #f0f0f0;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>Otros Ingresos:</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{self.other_income or 0:,.2f}</td>
                </tr>
                {source_info}
                <tr style="background: #d4edda;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>ISR Mensual:</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right; font-size: 18px;"><b>{self.amount_isr:,.2f}</b></td>
                </tr>
                <tr style="background: #d1ecf1;">
                    <td style="padding: 8px; border: 1px solid #ddd;"><b>ISR por Periodo:</b></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right; font-size: 18px;"><b>{self.value_isr:,.2f}</b></td>
                </tr>
            </table>
            <p style="margin-top: 15px; color: #666;">
                📝 <b>Nota:</b> El ISR se toma directamente del reporte ISR cuando está disponible.
            </p>
        </div>
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('ISR Sincronizado'),
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }

    @api.depends('schedule_pay', 'wage')
    def _compute_montly_salary(self):
        for contract in self:
            montly_salary = contract.wage * FREQUENCY_MULTIPLIER_v2.get(
                contract.schedule_pay, 1)
            contract.montly_salary = montly_salary

    def write(self, vals):
        for contract in self:
            # Valores anteriores
            previous_department = None
            previous_job = None
            previous_wage = contract.wage
            previous_montly_salary = contract.montly_salary
            previous_schedule_pay = contract.schedule_pay
            if contract.department_id:
                if contract.department_id.record_salary_history:
                    previous_department = contract.department_id.id

                    if contract.job_id:
                        previous_job = contract.job_id.id

                    # Valores estaticos
                    contract_id = contract.id
                    employee_id = contract.employee_id.id
                    # Evaluo si se cambio el salario
                    if vals.get('wage'):
                        # Busco si el contrato ya tiene historial de salarios
                        history = self.env['hr.hn.salary.history'].search(
                            [('contract_id', '=', contract_id),
                             ('employee_id', '=', employee_id)], limit=1,
                            order="create_date desc")
                        # Si existe tomo la fecha de fin del ultimo historial como fecha de inicio para el nuevo registro
                        if history:
                            initial_date = history.end_date
                        # Si no existe tomo la fecha de inicio del contrato como fecha de inicio para el nuevo registro
                        else:
                            initial_date = contract.date_start
                        # Llamo la funcion y mando los parametros
                        self.register_salary_history(contract_id, employee_id,
                                                     previous_department, previous_job,
                                                     previous_wage, previous_schedule_pay,
                                                     previous_montly_salary, initial_date)

        return super().write(vals)

    def register_salary_history(self, contract, employee, previous_department,
                                previous_job, previous_wage, previous_schedule_pay,
                                previous_montly_salary, initial_date):
        history = self.env['hr.hn.salary.history']
        today = datetime.now() - timedelta(hours=6)
        vals = {
            'contract_id': contract,
            'employee_id': employee,
            'department_id': previous_department,
            'job_id': previous_job,
            'salary': previous_wage,
            'schedule_pay': previous_schedule_pay,
            'montly_salary': previous_montly_salary,
            'initial_date': initial_date,
            'end_date': today.date()
        }
        history.create(vals)