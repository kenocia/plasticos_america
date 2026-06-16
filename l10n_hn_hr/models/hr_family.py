# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields, _

GENDER_SELECTION = [('male', 'Male'),
                    ('female', 'Female')]

KINDRED_SELECTION = [('mother', _('Mother')),
                     ('father', _('Father')),
                     ('son', _('Son')),
                     ('brother', _('Brother')),
                     ('sister', _('Sister')),
                     ('wife', _('Wife')),
                     ('husband', _('Husband')),
                     ('grandfather', _('Grandfather')),
                     ('cousin', _('Cousin')),
                     ('uncle', _('Uncle'))]


class HrFamily(models.Model):
    _name = 'hr.family'
    _description = 'HR Employee families'

    employee_id = fields.Many2one(string="Empleado", comodel_name='hr.employee')
    name = fields.Char(string="Nombre", required=True)
    date_of_birth = fields.Date(string="Fecha de Nacimiento")
    kindred = fields.Selection(
        string='Parentesco',
        selection=KINDRED_SELECTION
    )
    gender = fields.Selection(
        string='Género',
        selection=GENDER_SELECTION
    )
    conviviality = fields.Boolean(string="Convivencia", default=True)
