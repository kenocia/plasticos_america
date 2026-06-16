# -*- coding: utf-8 -*-

from odoo import models, fields, api


class REsCompany(models.Model):
    _inherit = 'res.company'

    day_internal_published = fields.Integer(string="Cantidad de días publicada")
    selection_portal = fields.Many2many('hr.employee', string='Selección portal', readonly=False)

