from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HrHnBenefitDeductionHistory(models.Model):
    _name = 'hr.hn.benefit.deduction.history'
    _description = 'Beneficios y deducciones historial'

    employee_id = fields.Many2one(string="Empleado", comodel_name="hr.employee")
    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract")
    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    job_id = fields.Many2one(string="Puesto de trabajo", comodel_name="hr.job")
    payslip_run_id = fields.Many2one(string="Lote de nómina", comodel_name="hr.payslip.run")
    payslip_id = fields.Many2one(string="Recibo de nómina", comodel_name="hr.payslip")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente')])
    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio')])
    rule_id = fields.Many2one(string="Regla", comodel_name="hr.salary.rule")
    fee_amount = fields.Float(string="Monto cuota")
    fee_amount_apply = fields.Float(string="Monto cuota aplicar")
    apply_in = fields.Selection(string="Aplicar en", selection=[('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')])
    periodicity = fields.Selection(string="Periodicidad", selection=[('finite','Finito'),('infinite','Infinito')])
    salary = fields.Float(string="Salario")
    montly_salary = fields.Float(string="Salario mensual")
    salary_pay = fields.Float(string="Salario pagado")
    initial_date = fields.Date(string="Periodo desde")
    end_date = fields.Date(string="Periodo hasta")