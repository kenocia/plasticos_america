from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import datetime, timedelta, time
import io
import openpyxl
import base64

class HrHnAssignBenefitDeduction(models.Model):
    _name = 'hr.hn.assign.benefit.deduction'
    _description = "Asignación de beneficios y deduicciones"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char(string="Nombre", compute="_compute_name", store=True, readonly=True)
    company_id = fields.Many2one(string="Compañía", comodel_name="res.company", required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department", check_company=True)
    type = fields.Selection(string="Tipo", selection=[('fixed','Fijo'),('variable','Variable')])
    amount = fields.Float(string="Monto")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente')])
    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio')], required=True)
    rule_id = fields.Many2one(string="Regla", comodel_name="hr.salary.rule", required=True)
    apply_in = fields.Selection([('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    periodicity = fields.Selection(string="Periodicidad", selection=[('finite','Finito'),('infinite','Infinito')], required=True)
    start_date = fields.Date(string="Fecha de inicio")
    fee_numbers = fields.Integer(string="Número de cuotas", help="Cantidad de cuotas totales que se deducirán. (cuotas segun la periodicidad de pago)")
    line_ids = fields.One2many(string="Lineas de asignación de beneficios y deducciones", comodel_name="hr.hn.assign.benefit.deduction.line", inverse_name="assign_id")
    state = fields.Selection(string=_('State'), selection=[('draft', _('Borrador')),('done', _('Aplicado')),], default='draft',)
    file = fields.Binary(string='Archivo', help="El formato de excel requerido debe contener 2 columnas, en la primera un encabezado de nombre de empleado y en la segunda monto")
    payslip_batch_id = fields.Many2one(string="Lote de Nóminas", comodel_name="hr.payslip.run", help="Lote de nóminas donde se aplicará esta asignación", check_company=True)
    payslip_batch_name = fields.Char(string="Nombre del Lote", related="payslip_batch_id.name", readonly=True, store=True)
    
    # Campos de auditoría
    create_uid = fields.Many2one(string="Creado por", comodel_name="res.users", readonly=True)
    create_date = fields.Datetime(string="Fecha de creación", readonly=True)
    write_uid = fields.Many2one(string="Modificado por", comodel_name="res.users", readonly=True)
    write_date = fields.Datetime(string="Fecha de modificación", readonly=True)

    @api.depends('rule_id', 'payslip_batch_id', 'create_date')
    def _compute_name(self):
        for record in self:
            if record.rule_id and record.payslip_batch_id:
                record.name = f"{record.rule_id.name} - {record.payslip_batch_id.name}"
            elif record.rule_id:
                record.name = f"{record.rule_id.name} - {record.create_date.strftime('%Y-%m-%d') if record.create_date else 'Nuevo'}"
            else:
                record.name = f"Asignación - {record.create_date.strftime('%Y-%m-%d') if record.create_date else 'Nuevo'}"


    def process_file(self):
        if not self.file:
            raise ValidationError('Debe cargar el archivo para poder procesarlo')
        
        try:
            excel_data = base64.b64decode(self.file)
            excel_buffer = io.BytesIO(excel_data)
            workbook = openpyxl.load_workbook(excel_buffer)
            worksheet = workbook.active
            line = self.env['hr.hn.assign.benefit.deduction.line']
            vals = []
            row_number = 1  # Para tracking de errores
            
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                row_number += 1
                try:
                    # Validar que la fila no esté vacía
                    if not row or len(row) < 2:
                        continue
                    
                    # Validar que el nombre del empleado no esté vacío
                    employee_name = row[0]
                    if not employee_name or employee_name == '' or employee_name is None:
                        continue
                    
                    # Validar que el monto no esté vacío y sea convertible a float
                    amount_value = row[1]
                    if amount_value is None or amount_value == '':
                        continue
                    
                    # Buscar empleado
                    employee = self.env['hr.employee'].search([('name','=',employee_name),('company_id','=',self.company_id.id)], limit=1)
                    if not employee:
                        raise ValidationError(f'Fila {row_number}: No se encontró el empleado con el nombre: {employee_name} en la compañía {self.company_id.name}')
                    
                    # Convertir monto a float
                    try:
                        amount = float(amount_value)
                        if amount <= 0:
                            raise ValidationError(f'Fila {row_number}: El monto debe ser mayor a cero para {employee_name}')
                    except (ValueError, TypeError) as e:
                        raise ValidationError(f'Fila {row_number}: Error al convertir el monto "{amount_value}" a número para {employee_name}')
                    
                    vals.append({
                        'employee_id': employee.id,
                        'amount': amount,
                        'assign_id': self.id
                    })
                    
                except ValidationError:
                    raise  # Re-lanzar ValidationError para mantener el mensaje específico
                except Exception as e:
                    raise ValidationError(f"Fila {row_number}: Error inesperado al procesar: {e}")
            
            if len(vals) > 0:
                line.create(vals)
            else:
                raise ValidationError('No se encontraron registros válidos en el archivo Excel. Verifique que las columnas contengan datos válidos.')
                
        except ValidationError:
            raise  # Re-lanzar ValidationError para mantener el mensaje específico
        except Exception as e:
            raise ValidationError(f"Error al procesar el archivo Excel: {e}")
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    def action_done(self):
        self.write({'state': 'done'})

    def get_employees(self):
        line = self.env['hr.hn.assign.benefit.deduction.line']
        line.search([('assign_id','=',self.id)]).unlink()
        
        employees = []
        domain = [('company_id','=',self.company_id.id)]
        if self.department_id:
            domain = expression.AND([
                domain,
                [('department_id', 'child_of', self.department_id.id)]
            ])
        if self.schedule_pay:
            domain = expression.AND([
                domain,
                [('contract_ids.schedule_pay', '=', self.schedule_pay)]
            ])
        employee_ids = self.env['hr.employee'].search(domain)
        if self.type == 'fixed':
            amount = self.amount
        else:
            amount = 0
        for employee in employee_ids:
            vals = {
                'assign_id': self.id,
                'employee_id': employee.id,
                'amount': amount
            }
            employees.append(vals)

        return line.create(employees)


    def apply_assignment(self):
        frequency_multiplier = {
            'annually': 12,
            'semi-annually': 6,
            'quarterly': 4,
            'bi-monthly': 2,
            'bi-weekly': 0.5,
        }
        values = []
        bd = self.env['hr.hn.benefit.deduction']
        for line in self.line_ids:
            amount = 0
            contract_id = self.env['hr.contract'].search([('employee_id','=',line.employee_id.id),('state','=','open')], limit=1)
            if not contract_id:
                raise ValidationError(f"El empleado {line.employee_id.name} no cuenta con un contrato vigente.")
            
            benefit_deduction = bd.search([('contract_id','=',contract_id.id),('rule_id','=',self.rule_id.id),('state','in',['progress'])])
            if benefit_deduction:
                raise ValidationError(f"Ya existe un beneficio/deduccion activa de {self.rule_id.name} para el contrato de {line.employee_id.name}.")
            
            if self.schedule_pay != contract_id.schedule_pay:
                raise ValidationError(f"El empleado {line.employee_id.name} cuenta con un pago programado distinto al que se quiere aplicar.")
            
            if line.amount < 1:
                raise ValidationError(f"El monto del empleado {line.employee_id.name} debe de ser mayor a cero.")
            
            if self.schedule_pay == 'weekly':
                fee_amount_apply = line.amount / (1/4)
            else:
                fee_amount_apply = line.amount / frequency_multiplier.get(self.schedule_pay, 1)

            if self.schedule_pay == 'bi-weekly':
                if self.apply_in == 'both':
                    amount = fee_amount_apply
                else:
                    amount = fee_amount_apply / 2
            else:
                amount = fee_amount_apply
            
            vals = {
                'category': self.category,
                'rule_id': self.rule_id.id,
                'state': 'progress',
                'periodicity': self.periodicity,
                'fee_amount': amount,
                'fee_amount_apply': line.amount,
                'description': line.description,
                'schedule_pay': self.schedule_pay,
                'apply_in': self.apply_in,
                'contract_id': contract_id.id,
                'start_date': self.start_date,
                'fee_numbers': self.fee_numbers
            }
            values.append(vals)

        bd.create(values)
        self.action_done()

    def action_update_payment_status(self):
        """Actualizar manualmente el estado de pago y vinculación con lotes"""
        self.ensure_one()
        
        if not self.start_date:
            raise ValidationError("No se puede actualizar el estado sin una fecha de inicio definida")
        
        # Buscar lotes de nóminas que coincidan con el rango de fechas
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '<=', self.start_date),
            ('date_end', '>=', self.start_date),
            ('state', 'in', ['done', 'paid']),
            ('company_id', '=', self.company_id.id)
        ])
        
        updated_lines = 0
        linked_batches = 0
        
        for line in self.line_ids:
            # Limpiar vinculaciones existentes
            line.payslip_batch_ids = [(5, 0, 0)]
            
            # Vincular con lotes que coincidan
            for payslip_run in payslip_runs:
                line.payslip_batch_ids = [(4, payslip_run.id)]
                linked_batches += 1
            
            # Forzar recálculo del estado
            line._compute_payment_status()
            updated_lines += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Estado actualizado: {updated_lines} líneas procesadas, {linked_batches} vinculaciones realizadas',
                'type': 'success',
            }
        }

class HrHnAssignBenefitDeductionLine(models.Model):
    _name = 'hr.hn.assign.benefit.deduction.line'
    _description = "Lineas de asignación de beneficios y deduicciones"
    _check_company_auto = True

    company_id = fields.Many2one(string="Compañía", comodel_name="res.company", required=True, default=lambda self: self.env.company, related="assign_id.company_id", store=True)
    employee_id = fields.Many2one(string="Empleado", comodel_name="hr.employee", check_company=True)
    description = fields.Char(string="Descripción")
    amount = fields.Float(string="Monto")
    assign_id = fields.Many2one(string="", comodel_name="hr.hn.assign.benefit.deduction", required=True, ondelete='cascade')
    payslip_batch_ids = fields.Many2many(string="Lotes de Nóminas", comodel_name="hr.payslip.run", help="Lotes de nóminas donde se aplicará esta asignación", check_company=True)
    payment_status = fields.Selection(string="Estado de Pago", selection=[
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado')
    ], default='pending', compute='_compute_payment_status', store=True)

    @api.depends('payslip_batch_ids', 'payslip_batch_ids.state')
    def _compute_payment_status(self):
        """Calcular el estado de pago basado en los lotes de nóminas vinculados"""
        for line in self:
            if not line.payslip_batch_ids:
                line.payment_status = 'pending'
            else:
                # Si hay lotes vinculados, verificar su estado
                paid_batches = line.payslip_batch_ids.filtered(lambda b: b.state in ['done', 'paid'])
                cancelled_batches = line.payslip_batch_ids.filtered(lambda b: b.state == 'cancel')
                
                if paid_batches:
                    line.payment_status = 'paid'
                elif cancelled_batches and not paid_batches:
                    line.payment_status = 'cancelled'
                else:
                    line.payment_status = 'pending'

    def action_update_line_payment_status(self):
        """Actualizar estado de pago de una línea individual"""
        self.ensure_one()
        
        if not self.assign_id or not self.assign_id.start_date:
            raise ValidationError("No se puede actualizar el estado sin una fecha de inicio definida")
        
        # Buscar lotes de nóminas que coincidan con el rango de fechas
        payslip_runs = self.env['hr.payslip.run'].search([
            ('date_start', '<=', self.assign_id.start_date),
            ('date_end', '>=', self.assign_id.start_date),
            ('state', 'in', ['done', 'paid']),
            ('company_id', '=', self.company_id.id)
        ])
        
        # Limpiar vinculaciones existentes
        self.payslip_batch_ids = [(5, 0, 0)]
        
        # Vincular con lotes que coincidan
        for payslip_run in payslip_runs:
            self.payslip_batch_ids = [(4, payslip_run.id)]
        
        # Forzar recálculo del estado
        self._compute_payment_status()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Estado actualizado para {self.employee_id.name}: {len(payslip_runs)} lotes vinculados',
                'type': 'success',
            }
        }
    
    