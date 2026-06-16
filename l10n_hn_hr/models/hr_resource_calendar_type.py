# -*- coding: utf-8 -*-

from odoo import api, fields, models, modules


class HrResourceCalendarType(models.Model):
    _name = 'hr.resource.calendar.type'
    _description = 'Tipos de horarios de trabajo'
    _rec_name = 'name'

    code = fields.Char(string='Código', required=True)
    name = fields.Char(string="Tipo de horario", required=True)

