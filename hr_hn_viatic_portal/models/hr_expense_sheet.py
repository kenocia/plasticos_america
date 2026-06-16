# -*- coding: utf-8 -*-

from odoo import api, fields, Command, models, _

class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    viatic_id = fields.Many2one(
    comodel_name='hr.hn.viatic',
    string="Viatic Reference",
    help="Reference to the related viatic report.",
    ondelete='set null') # Si se borra el viático, el campo se pone en NULL
