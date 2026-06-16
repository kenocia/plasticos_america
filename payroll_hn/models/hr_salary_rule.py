# -*- coding:utf-8 -*-
from odoo import _, api, fields, models

class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Sirve para determinar que las reglas que tengan este check se podrán utilizar en los beneficios y deducciones.
    benefit_deduction = fields.Boolean(string="Beneficio/Deduccion", default=False, help="Las reglas que tengan este check podran utilizarce como beneficio o deducción en el contrato")