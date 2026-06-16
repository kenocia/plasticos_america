from odoo import fields, models, api


class HolidaysType(models.Model):
    _inherit = 'hr.leave.type'

    only_to_pay = fields.Boolean('Solo a pagar', default=False)
