# -*- coding: utf-8 -*-

from odoo import api, fields, models, modules


class AuthorizedSignature(models.Model):
    _name = 'hr.authorized.signature'
    _description = 'Firmas autorizadas'
    _rec_name = 'model'

    model = fields.Many2one('ir.model', 'Model')
    employee_ids = fields.Many2many('hr.employee', string='Autorizados')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env['res.company']._company_default_get())
