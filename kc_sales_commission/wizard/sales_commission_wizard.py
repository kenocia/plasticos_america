# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class KcSalesCommissionWizard(models.TransientModel):
    _name = 'kc.sales.commission.wizard'
    _description = 'Generar cálculo de comisión'

    date_from = fields.Date(string='Fecha inicial', required=True)
    date_to = fields.Date(string='Fecha final', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)

    def action_generate_commission(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('La fecha inicial no puede ser posterior a la fecha final.'))
        if not self.employee_id:
            raise UserError(_('Debe seleccionar un empleado.'))

        commission = self.env['kc.sales.commission'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company_id.id,
            'employee_id': self.employee_id.id,
            'state': 'draft',
        })
        commission.generate_commission_lines()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Cálculo de comisión'),
            'res_model': 'kc.sales.commission',
            'res_id': commission.id,
            'view_mode': 'form',
            'target': 'current',
        }
