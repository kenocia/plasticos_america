# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class HrBloodType(models.Model):
    _name = 'hr.blood.type'
    _description = 'HR Blood Type'

    code = fields.Char(string='Code Blood Type', required=True)
    name = fields.Char(string='Blood Type', required=True)

