# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class KcSalesCommissionPaymentWizard(models.TransientModel):
    _name = 'kc.sales.commission.payment.wizard'
    _description = 'Registrar pago de comisión'

    commission_id = fields.Many2one(
        'kc.sales.commission',
        string='Comisión',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Beneficiario',
        required=True,
        help='Contacto al que se registra el pago (normalmente el contacto laboral del empleado).',
    )
    amount = fields.Monetary(
        string='Importe',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
    )
    payment_date = fields.Date(
        string='Fecha de pago',
        required=True,
        default=fields.Date.context_today,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario de pago',
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
    )
    memo = fields.Char(string='Referencia / memo')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cid = self.env.context.get('default_commission_id') or self.env.context.get('active_id')
        if cid and 'commission_id' in fields_list:
            comm = self.env['kc.sales.commission'].browse(cid)
            if comm.exists():
                res['commission_id'] = comm.id
                res['company_id'] = comm.company_id.id
                res['currency_id'] = comm.currency_id.id
                pending = comm.commission_pending_balance
                if comm.currency_id:
                    pending = comm.currency_id.round(pending or 0.0)
                res['amount'] = pending if pending > 0 else comm.total_commission
                emp = comm.employee_id
                partner = emp.work_contact_id or emp.user_id.partner_id
                if partner:
                    res['partner_id'] = partner.id
                journal = self.env['account.journal'].search(
                    [
                        ('type', 'in', ('bank', 'cash')),
                        ('company_id', '=', comm.company_id.id),
                    ],
                    limit=1,
                )
                if journal:
                    res['journal_id'] = journal.id
                res['memo'] = _('Comisión %s') % (comm.name,)
        return res

    def action_create_payment(self):
        self.ensure_one()
        comm = self.commission_id
        if comm.state == 'locked':
            raise UserError(_('La comisión está bloqueada; no puede registrar pagos.'))
        if comm.state not in ('confirmed', 'payment_posted', 'payment_draft'):
            raise UserError(_('No puede registrar el pago en el estado actual de la comisión.'))
        pending_bal = comm.commission_pending_balance
        if comm.currency_id:
            pending_bal = comm.currency_id.round(pending_bal or 0.0)
        else:
            pending_bal = pending_bal or 0.0
        if pending_bal <= 0:
            raise UserError(_('No hay saldo pendiente de comisión por pagar.'))
        if not self.partner_id:
            raise UserError(_('Debe indicar el beneficiario del pago.'))
        if self.amount <= 0:
            raise UserError(_('El importe del pago debe ser positivo.'))

        journal = self.journal_id
        method_line = journal.outbound_payment_method_line_ids[:1]
        if not method_line:
            raise UserError(
                _('El diario %s no tiene método de pago de salida configurado.') % (journal.display_name,)
            )

        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.payment_date,
            'journal_id': journal.id,
            'payment_method_line_id': method_line.id,
            'memo': self.memo or _('Comisión %s') % (comm.name,),
            'commission_id': comm.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }
