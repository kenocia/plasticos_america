# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint

from odoo import fields, models


class EmployeeStaffDivision(models.Model):
    _name = "hr.employee.sucursal"
    _description = "Sucursal"

    code = fields.Char('Código', required=True)
    name = fields.Char(string="Sucursal", translate=True, required=True)
    employee_company_id = fields.Many2one('hr.employee.company', string="Empresa", required=True)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', "El código ya existe !"),
    ]
