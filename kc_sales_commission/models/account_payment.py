# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    commission_id = fields.Many2one(
        'kc.sales.commission',
        string='Comisión de ventas',
        ondelete='set null',
        copy=False,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments.mapped('commission_id')._sync_state_from_payments()
        return payments

    def write(self, vals):
        old_commissions = self.mapped('commission_id')
        res = super().write(vals)
        (old_commissions | self.mapped('commission_id'))._sync_state_from_payments()
        return res

    def unlink(self):
        commissions = self.mapped('commission_id')
        res = super().unlink()
        commissions._sync_state_from_payments()
        return res
