# -*- coding:utf-8 -*-
from odoo import _, api, fields, models

class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio'),('BASIC','Salario básico')])