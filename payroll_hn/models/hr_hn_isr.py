from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


class HrHnIsr(models.Model):
    _name = 'hr.hn.isr'
    _description = 'ISR HN'
    _inherit = ['mail.thread']

    name = fields.Char(string="Nombre", required=True, tracking=True, copy=False)
    company_id = fields.Many2one(string='Compañía', comodel_name='res.company',
                                 default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency',
                                  default=lambda
                                      self: self.env.user.company_id.currency_id.id,
                                  required=True)
    state = fields.Selection(string="Estado",
                             selection=[('draft', 'Inactivo'), ('active', 'Activo'), ],
                             default='draft', tracking=True)
    exempt_salary = fields.Float(string="Salario Exento")
    medical_expense = fields.Float(string="Gastos Médicos")
    range_ids = fields.One2many(string="Rangos", comodel_name="hr.hn.isr.ranges",
                                inverse_name="isr_id")
    contract_count = fields.Integer(string="Contratos", compute="_compute_count")
    isr_line_ids = fields.One2many("hn.isr.line", "parent_id", "Detail")

    def _compute_count(self):
        for isr in self:
            contracts = self.env['hr.contract'].search_count([
                ('isr_id', '=', isr.id),
                ('company_id', '=', isr.company_id.id)
            ])
            isr.contract_count = contracts

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)', '¡El nombre debe ser único por compañía!'),
    ]

    """ Verifica y valida que solo pueda existir un registro activo a la vez por compañía. """

    @api.constrains('state', 'company_id')
    def _check_unique_active_state(self):
        for record in self:
            active_records = self.search_count([
                ('state', '=', 'active'), 
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id)
            ])
            if record.state == 'active' and active_records > 0:
                raise ValidationError(f"¡Ya existe un registro activo para la compañía {record.company_id.name}!")

    def delete_lines(self):
        """
            This method clean all the lines of the report.
        """
        for r in self:
            for line in r.isr_line_ids:
                line.unlink()
            r.action_draft()

    def set_isr_amount_on_contracts(self):
        """
            Sincroniza los valores ISR del reporte a los contratos.
            Ahora que amount_isr y value_isr son campos computados que toman los valores del reporte,
            solo necesitamos forzar el recálculo para que se actualicen.
        """

        for r in self:
            contracts_updated = 0
            for line in r.isr_line_ids:
                # Verificar que el contrato pertenece a la compañía del registro ISR
                if line.contract_id.company_id == r.company_id:
                    # Forzar recálculo para que tome el valor del reporte ISR
                    line.contract_id._compute_isr()
                    
                    contracts_updated += 1
                    _logger.info(f"  → {line.employee_id.name}: ISR sincronizado = {line.isr_fee:.2f}")
            
            if contracts_updated > 0:
                _logger.info(f"✓ {contracts_updated} contratos sincronizados con valores ISR")

    """ Establece el estado como borrador. """

    def action_draft(self):
        self.write({'state': 'draft'})

    """ Establece el estado como activo. """

    def action_active(self):
        self.write({'state': 'active'})


    def get_isr_table(self):
        for r in self:
            # Filtrar contratos por compañía del registro ISR y ISR
            contracts = self.env['hr.contract'].search([
                ('isr_id', '=', r.id),
                ('company_id', '=', r.company_id.id)
            ])
            _logger.info(f"Contratos encontrados para la compañía {r.company_id.name}: {len(contracts)}")
            for contract in contracts:
                total_incomes = 0
                isr = 0
                isr_periodicity = 0
                retention_total = 0
                months_worked = 0
                his_months_worked = 0
                different_months = []
                amount_rap = 0
                amount_ivm = 0
                total_base = 0

                # Calcular meses trabajados en el año actual
                start_date = contract.date_start
                current_date = fields.Date.today()
                
                # Obtener el primer día del año actual
                first_day_current_year = datetime(current_date.year, 1, 1).date()
                
                # Calcular meses trabajados desde el inicio del año o desde la fecha de inicio del contrato
                if start_date < first_day_current_year:
                    # El contrato empezó antes del año actual
                    months_worked = 12  # Trabajó todo el año
                else:
                    # El contrato empezó durante el año actual
                    delta = current_date - start_date
                    months_worked = max(1, delta.days // 30)  # Mínimo 1 mes
                    if months_worked > 12:
                        months_worked = 12

                # Calcular total_incomes como salario anual (salario mensual * 12)
                # Esto garantiza que el salario anual sea exactamente el salario mensual multiplicado por 12
                total_incomes = contract.montly_salary * 12

                # Procesar historial de salarios para calcular meses trabajados
                history = self.env['hr.hn.salary.history'].search(
                    [('contract_id', '=', contract.id),
                     ('employee_id', '=', contract.employee_id.id)],
                    order="create_date desc")
                
                if history:
                    for his in history:
                        if his.initial_date not in different_months:
                            different_months.append(his.initial_date)
                            delta = his.end_date - his.initial_date
                            his_months_worked += delta.days // 30
                            # NO sumar al total_incomes - solo usar para calcular meses trabajados

                # Calcular RAP e IVM basado en los meses trabajados
                total_months = months_worked + his_months_worked
                amount_rap = contract.amount_rap * total_months
                amount_ivm = contract.ihss_id.fee_ivm * total_months

                # Creamos las lineas del reporte
                r.isr_line_ids = [(0, 0, {
                    'montly_salary': contract.montly_salary,  # Salario mensual calculado
                    'employee_id': contract.employee_id.id,
                    'contract_id': contract.id,
                    'parent_id': r.id,
                    'medical_expense': r.medical_expense,
                    'amount_rap': amount_rap,
                    'amount_ivm': amount_ivm,
                    'total_incomes': total_incomes,  # Salario anual (mensual * 12)
                    'months_worked': months_worked,
                    'his_months_worked': his_months_worked,
                })]
            
            # Asignar los valores calculados a los contratos después de crear las líneas
            r.set_isr_amount_on_contracts()
            _logger.info(f"✓ Valores ISR asignados a {len(contracts)} contratos de la compañía {r.company_id.name}")
        
        # Mostrar mensaje de confirmación en la UI
        # Sincronizar "Otros Ingresos" del reporte ISR a los contratos
        self._sync_other_income_to_contracts()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('¡Éxito!'),
                'message': _('Se han calculado y asignado los valores ISR a los contratos.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _sync_other_income_to_contracts(self):
        """Sincroniza los 'Otros Ingresos' del reporte ISR a los contratos"""
        for r in self:
            for line in r.isr_line_ids:
                if line.contract_id and line.other_income:
                    # Actualizar el campo other_income en el contrato
                    line.contract_id.other_income = line.other_income
                    _logger.info(f"  → {line.employee_id.name}: Otros Ingresos sincronizados = {line.other_income:,.2f}")
            
            _logger.info(f"✓ Otros Ingresos sincronizados para la compañía {r.company_id.name}")


class HrHnIsrRanges(models.Model):
    _name = "hr.hn.isr.ranges"
    _description = "ISR HN rangos"

    isr_id = fields.Many2one(string="ISR", comodel_name="hr.hn.isr")
    amount_from = fields.Float("Desde", required=True)
    amount_to = fields.Float("Hasta", required=True)
    rate = fields.Float("Tasa %", required=True)
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency',
                                  default=lambda
                                      self: self.env.user.company_id.currency_id.id,
                                  required=True)


class HrHnIsrAssign(models.TransientModel):
    _name = 'hr.hn.isr.assign'
    _description = 'Asignar ISR'

    def _get_available_contracts_domain(self):
        return [('company_id', '=', self.env.company.id)]

    def _get_employees(self):
        return self.env['hr.employee'].search(self._get_available_contracts_domain())

    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    schedule_pay = fields.Selection(string="Pago programado",
                                    selection=[('annually', 'Anualmente'),
                                               ('semi-annually', 'Semestralmente'),
                                               ('quarterly', 'Trimestral'),
                                               ('bi-monthly', 'Bimestral'),
                                               ('monthly', 'Mensual'),
                                               ('bi-weekly', 'Quincenal'),
                                               ('weekly', 'Semanalmente')])
    apply_in = fields.Selection(
        [('first', 'Primera quincena'), ('second', 'Segunda quincena'),
         ('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_isr_assign_rel',
                                    'assign_id', 'employee_id', 'Employees',
                                    default=lambda self: self._get_employees(),
                                    required=True, compute='_compute_employee_ids',
                                    store=True, readonly=False)

    @api.depends('department_id', 'schedule_pay')
    def _compute_employee_ids(self):
        for wizard in self:
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND([
                    domain,
                    [('department_id', 'child_of', self.department_id.id)]
                ])
            if wizard.schedule_pay:
                domain = expression.AND([
                    domain,
                    [('contract_ids.schedule_pay', '=', self.schedule_pay)]
                ])
            wizard.employee_ids = self.env['hr.employee'].search(domain)

    def action_assign(self):
        if not self.employee_ids:
            raise ValidationError(
                _('No se puede asignar cuentas a reglas si no hay empleados seleccionados.'))

        contracts_updated = 0
        for employee in self.employee_ids:
            contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', employee.id), ('state', '=', 'open')], limit=1)
            
            if not contract_id:
                raise ValidationError(
                    f"El empleado {employee.name} no cuenta con un contrato vigente.")
            
            # Filtrar ISR activo por compañía del contrato
            isr_id = self.env['hr.hn.isr'].search([
                ('state', '=', 'active'),
                ('company_id', '=', contract_id.company_id.id)
            ], limit=1)

            if not isr_id:
                raise ValidationError(
                    f"No existe un registro ISR activo para la compañía {contract_id.company_id.name}.")

            if self.schedule_pay != contract_id.schedule_pay:
                raise ValidationError(
                    f"El empleado {employee.name} cuenta con un pago programado distinto al que se quiere aplicar.")

            # Asignar el ISR al contrato
            if self.schedule_pay == 'bi-weekly':
                contract_id.write({
                    'apply_isr': True, 
                    'isr_id': isr_id.id,
                    'apply_in_isr': self.apply_in
                })
            else:
                contract_id.write({
                    'apply_isr': True, 
                    'isr_id': isr_id.id
                })
            
            # Forzar el recálculo del ISR
            contract_id._compute_isr()
            contracts_updated += 1
            _logger.info(f"ISR asignado a {employee.name}: amount_isr={contract_id.amount_isr}, value_isr={contract_id.value_isr}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('¡Éxito!'),
                'message': _('ISR asignado exitosamente a %s contratos.') % contracts_updated,
                'type': 'success',
                'sticky': False,
            }
        }


class HnIsrLine(models.Model):
    _name = 'hn.isr.line'
    _description = 'HnIsrLine'

    _rec_name = 'employee_id'
    _order = 'employee_id ASC'

    parent_id = fields.Many2one("hr.hn.isr", "Hn Settings")
    employee_id = fields.Many2one("hr.employee", "Empleado", required=True)
    contract_id = fields.Many2one("hr.contract", "Contrato")
    total_incomes = fields.Float("Salario Anual")
    amount_membership = fields.Float("Colegiaturas")
    medical_expense = fields.Float("Gastos Médicos")
    amount_rap = fields.Float("RAP")
    amount_ivm = fields.Float("Invalidez Vejez y Muerte")
    other_expenses = fields.Float("Otros Gastos")
    total_base = fields.Float("Total Base Impositiva", compute='_compute_isr_values')
    total_tax = fields.Float("Total Impuesto", compute='_compute_isr_values')
    isr_fee = fields.Float("Deducción", compute='_compute_isr_values')
    pay_periodicity = fields.Selection(
        [('bi-weekly', 'Quincenal'), ('monthly', 'Mensual')], "Periodicidad Pago",
        default='bi-weekly')
    montly_salary = fields.Float(string="Salario Mensual", readonly=True)
    other_income = fields.Float(string="Otros Ingresos")
    net_salary = fields.Float(string="Total Ingresos", compute='_compute_net_salary')
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.user.company_id)
    months_worked = fields.Integer(string="Meses trabajados")
    his_months_worked = fields.Integer(string="Meses trabajados HIS")
    months_to_divide = fields.Integer(string="Meses a Dividir", default=0)
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency',
                                  related='parent_id.currency_id')
    total_detained = fields.Float("Total Impuesto Retenido")

    @api.depends('total_incomes', 'other_income')
    def _compute_net_salary(self):
        for r in self:
            r.net_salary = r.total_incomes + r.other_income

    @api.depends('total_incomes', 'other_income', 'medical_expense', 'amount_rap',
                 'amount_ivm', 'other_expenses', 'amount_membership', 'total_detained')
    def _compute_isr_values(self):
        for r in self:
            retention_total = 0
            # Total Base = Salario Anual + Otros Ingresos
            total_base = r.total_incomes + r.other_income
            
            _logger.info(f"\n=== CÁLCULO ISR PARA {r.employee_id.name} ===")
            _logger.info(f"Salario Anual: {r.total_incomes}")
            _logger.info(f"Otros Ingresos: {r.other_income}")
            _logger.info(f"Total Base: {total_base}")
            _logger.info(f"Gastos Médicos: {r.medical_expense}")
            
            # Calcular ISR usando la tabla de rangos configurada
            # La deducción de gastos médicos solo se aplica al tramo del 15%
            annual_income = total_base
            
            # Ordenar rangos por amount_from para procesar correctamente
            ranges = r.parent_id.range_ids.sorted('amount_from')
            _logger.info(f"Rangos encontrados: {len(ranges)}")
            
            for i, range in enumerate(ranges):
                _logger.info(f"\n--- Rango {i+1} ---")
                _logger.info(f"Desde: {range.amount_from}")
                _logger.info(f"Hasta: {range.amount_to}")
                _logger.info(f"Tasa: {range.rate}%")
                
                if range.rate > 0 and annual_income > range.amount_from:
                    # Calcular el monto a gravar en este rango
                    if annual_income <= range.amount_to or range.amount_to == 0:
                        # El monto está dentro de este rango
                        amount_in_range = annual_income - range.amount_from
                        _logger.info(f"El ingreso está dentro del rango")
                    else:
                        # El monto excede este rango, tomar todo el rango
                        amount_in_range = range.amount_to - range.amount_from
                        _logger.info(f"El ingreso excede el rango, tomar todo el rango")
                    
                    _logger.info(f"Monto base en rango: {amount_in_range}")
                    
                    # Aplicar deducción de gastos médicos solo en el tramo del 15%
                    # (aproximadamente entre 217,493 y 331,638)
                    if range.rate == 0.15 and range.amount_from >= 217000 and range.amount_to <= 332000:
                        medical_deduction = min(r.medical_expense, 40000)
                        _logger.info(f"Aplicando deducción médica: {medical_deduction}")
                        amount_in_range = max(0, amount_in_range - medical_deduction)
                        _logger.info(f"Monto después de deducción médica: {amount_in_range}")
                    
                    # Aplicar la tasa del rango
                    # Si la tasa es menor a 1, asumir que ya está en decimal (0.15 = 15%)
                    # Si la tasa es mayor a 1, asumir que está en porcentaje (15 = 15%)
                    if range.rate < 1:
                        isr_rango = amount_in_range * range.rate
                    else:
                        isr_rango = amount_in_range * range.rate / 100
                    retention_total += isr_rango
                    _logger.info(f"ISR del rango: {isr_rango}")
                else:
                    _logger.info(f"Rango no aplicable (tasa 0 o ingreso menor al límite inferior)")

            _logger.info(f"\nTotal ISR calculado: {retention_total}")
            _logger.info(f"Total detenido: {r.total_detained}")
            
            # El ISR se calcula anualmente, dividir entre 12 para obtener el monto mensual
            isr = (retention_total - r.total_detained) / 12
            _logger.info(f"ISR anual: {retention_total - r.total_detained}")
            _logger.info(f"ISR mensual: {isr}")

            r.total_base = total_base
            r.total_tax = retention_total
            r.isr_fee = isr