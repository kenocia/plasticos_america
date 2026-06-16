# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint

from odoo import fields, models, api


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    department_type = fields.Selection([
        ('empresa', 'Empresa'),
        ('sucursal', 'Sucursal'),
        ('departamento', 'Departamento'),
        ('area', 'Area'),
        ('otro', 'Otro Nivel')
    ], string="Tipo de Departamento", store=True)

    level = fields.Integer(string="Nivel Jerárquico", compute='_compute_level', store=True, readonly=True)

    @api.depends('parent_id', 'parent_id.level')
    def _compute_level(self):
        for department in self:
            if department.parent_id:
                department.level = department.parent_id.level + 1
            else:
                department.level = 0


