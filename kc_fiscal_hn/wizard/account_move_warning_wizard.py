# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMoveWarningWizard(models.TransientModel):
    _name = 'account.move.warning.wizard'
    _description = 'Advertencia Fiscal al Validar Factura'

    warning_message = fields.Text(string="Mensaje de advertencia", readonly=True)
    move_id = fields.Many2one('account.move', string='Factura', readonly=True)
    warning_type = fields.Selection([
        ('date', 'Advertencia de Fecha'),
        ('numbers', 'Advertencia de Números'),
        ('general', 'Advertencia General')
    ], string='Tipo de Advertencia', default='general')
    
    def action_continue(self):
        """Continuar con la validación de la factura"""
        if self.move_id:
            return self.move_id.with_context(skip_fiscal_warning=True).action_post()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Cancelar la validación"""
        return {'type': 'ir.actions.act_window_close'}
    
    @api.model
    def create_warning(self, message, move_id, warning_type='general'):
        """Método de clase para crear advertencias"""
        return self.create({
            'warning_message': message,
            'move_id': move_id,
            'warning_type': warning_type
        })
