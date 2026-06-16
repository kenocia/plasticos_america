# -*- coding: utf-8 -*-

from odoo import models, fields


class HrWorkEntry(models.Model):
    # Private attributes
    _inherit = 'hr.work.entry'
    _description = 'HR Work Entry'

    # Fields declaration
    total_overtime = fields.Float(
        string="Extra Hours", 
        related='employee_id.total_overtime')
   