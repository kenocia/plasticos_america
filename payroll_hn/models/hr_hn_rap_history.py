from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HrHnRapHistory(models.Model):
    _name = 'hr.hn.rap.history'
    _description = 'RAP historial'

    employee_id = fields.Many2one(string="Empleado", comodel_name="hr.employee")
    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract")
    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    job_id = fields.Many2one(string="Puesto de trabajo", comodel_name="hr.job")
    rap_id = fields.Many2one(string="Parametro RAP", comodel_name="hr.hn.rap")
    payslip_run_id = fields.Many2one(string="Lote de nómina", comodel_name="hr.payslip.run")
    payslip_id = fields.Many2one(string="Recibo de nómina", comodel_name="hr.payslip")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('semi-monthly', 'Quincenal'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente'),('daily', 'Diario')])
    salary = fields.Float(string="Salario")
    montly_salary = fields.Float(string="Salario mensual")
    salary_pay = fields.Float(string="Salario pagado")
    amount_rap = fields.Float(string='Cuota RAP')
    value_rap = fields.Float(string='Monto RAP en nómina')
    apply_in_rap = fields.Selection(string="Aplicar RAP en", selection=[('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')])
    initial_date = fields.Date(string="Periodo desde")
    end_date = fields.Date(string="Periodo hasta")