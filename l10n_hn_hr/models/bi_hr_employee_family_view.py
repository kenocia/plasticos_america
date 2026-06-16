# -*- coding: utf-8 -*-

from psycopg2 import sql
from odoo import tools
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class HrEmployeeFamilyReport(models.Model):
    _name = "hr.employee.family.report"
    _description = 'Familiares del empleado'
    _auto = False
    _order = 'hr_employee_sucursal desc'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    hr_employee_company = fields.Char(string='Empresa')
    hr_employee_sucursal = fields.Char(string='Sucursal')
    nombre_familiar = fields.Char(string="Familiar")
    date_of_birth = fields.Date(string="Fecha de nacimiento")
    kindred = fields.Selection([
        ('mother', 'Madre'),
        ('father', 'Padre'),
        ('son', 'hijo'),
        ('brother', 'Hermano'),
        ('sister', 'Hermana'),
        ('wife', 'Esposa'),
        ('husband', 'Esposo'),
        ('grandfather', 'Abuelo'),
        ('cousin', 'Primo'),
        ('uncle', 'Tio')
    ], 'Parentezco')
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino')
    ], 'Sexo')
    conviviality = fields.Boolean(string="Convive", default=True)

    def init(self):
        query = """              
        SELECT concat(family.id::character varying, e.id::character varying)::integer AS id,
            e.hr_employee_company,
            e.hr_employee_sucursal,
            e.id as employee_id,
            family.name as nombre_familiar,
            family.date_of_birth,
            family.kindred,
            family.gender,
            family.conviviality
           FROM hr_family family  
             LEFT JOIN hr_employee e ON family.employee_id = e.id
         """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            sql.SQL("CREATE or REPLACE VIEW {} as ({})").format(
                sql.Identifier(self._table),
                sql.SQL(query)
            ))
