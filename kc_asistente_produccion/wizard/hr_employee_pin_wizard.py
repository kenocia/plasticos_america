# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class HrEmployeePinWizard(models.TransientModel):
    _name = 'hr.employee.pin.wizard'
    _description = 'Establecer PIN del empleado'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, readonly=True)
    pin = fields.Char(string='Nuevo PIN', required=True, password=True)
    pin_confirm = fields.Char(string='Confirmar PIN', required=True, password=True)

    def action_set_pin(self):
        self.ensure_one()
        if self.pin != self.pin_confirm:
            raise UserError(_('El PIN y la confirmación no coinciden.'))
        self.employee_id.set_pin(self.pin)
        return {'type': 'ir.actions.act_window_close'}
