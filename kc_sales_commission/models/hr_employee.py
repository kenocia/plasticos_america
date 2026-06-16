# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    commission_type = fields.Selection(
        [
            ('unit', 'Por unidad'),
            ('percent', 'Por porcentaje'),
        ],
        string='Tipo de comisión',
        default='unit',
        groups='hr.group_hr_user',
        tracking=True,
    )
    commission_rate = fields.Float(
        string='Valor comisión',
        digits=(16, 6),
        groups='hr.group_hr_user',
        tracking=True,
        help='Por unidad: monto por unidad vendida. Por porcentaje: porcentaje sobre la venta de línea.',
    )
    assigned_commission_client_ids = fields.One2many(
        'res.partner',
        'commission_employee_id',
        string='Clientes asignados',
        groups='hr.group_hr_user',
    )
    assigned_commission_client_count = fields.Integer(
        string='Nº clientes comisión',
        compute='_compute_assigned_commission_client_count',
    )

    @api.depends('assigned_commission_client_ids')
    def _compute_assigned_commission_client_count(self):
        for emp in self:
            emp.assigned_commission_client_count = len(emp.assigned_commission_client_ids)

    def action_open_commission_clients(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Clientes comisionados',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('commission_employee_id', '=', self.id)],
            'context': {'default_commission_employee_id': self.id},
        }
