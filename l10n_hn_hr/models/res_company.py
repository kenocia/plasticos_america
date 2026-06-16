# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Company(models.Model):
    _inherit = 'res.company'
    hide_fields = fields.Boolean(string='Ocultar', default=True, help='Ocultar campos que no son utilizados')
    authorized_signature_ids = fields.One2many('hr.authorized.signature', 'company_id', string='Autorizados')
