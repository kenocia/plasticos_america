# -*- coding:utf-8 -*-
from odoo import _, api, fields, models

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    record_salary_history = fields.Boolean(string="Registrar historial de salario para ISR", default=False, help="Este parametro permite que los empleados que pertenezcan a este departamento cuando sufran un cambio de salario, este deje registro historico del salario. Afecta el calculo de ISR")
    area = fields.Selection(string="Area", selection=[('admon','Administracion'),('vta','Ventas')])
