from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HrHnSalaryHistory(models.Model):
    _name = 'hr.hn.salary.history'
    _description = 'Hr Hn Salary History'

    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract")
    employee_id = fields.Many2one(string="Empleado", comodel_name="hr.employee")
    department_id = fields.Many2one(string="Departamento", comodel_name="hr.department")
    job_id = fields.Many2one(string="Puesto de trabajo", comodel_name="hr.job")
    salary = fields.Float(string="Salario")
    montly_salary = fields.Float(string="Salario mensual")
    schedule_pay = fields.Selection(string="Pago programado", selection=[('annually', 'Anualmente'),('semi-annually', 'Semestralmente'),('quarterly', 'Trimestral'),('bi-monthly', 'Bimestral'),('monthly', 'Mensual'),('semi-monthly', 'Quincenal'),('bi-weekly', 'Quincenal'),('weekly', 'Semanalmente'),('daily', 'Diario')])
    initial_date = fields.Date(string="Fecha de inicio")
    end_date = fields.Date(string="Fecha de fin")