# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    commission_employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado comisionista',
        tracking=True,
        help='Empleado que recibe comisión por ventas a este cliente.',
    )
