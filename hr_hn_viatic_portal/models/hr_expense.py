# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    approved_rate = fields.Monetary(string='Approved rate')
    qty_person = fields.Integer(string="Quantity")
    qty_days = fields.Integer(string="Quantity days")
    viatic_id = fields.Many2one(
        comodel_name='hr.hn.viatic',
        string="Expense Report",
        domain="[('employee_id', '=', employee_id), ('company_id', '=', company_id)]",
        readonly=True,
        copy=False,
    )
    payment_mode = fields.Selection(
        selection=[
            ('own_account', "Employee (to reimburse)"),
            ('company_account', "Company"),
            ('viatic', "Viatic"),
        ],
        string="Paid By",
        default='own_account',
        tracking=True,
    )
    # Campo product_id heredado del modelo base hr.expense
    # product_id = fields.Many2one(
    #     comodel_name='product.product',
    #     string="Category",
    #     tracking=True,
    #     check_company=True,
    #     domain=[('can_be_expensed', '=', True)],
    #     ondelete='restrict',
    # )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    sub_total_viatic_amount = fields.Monetary(string='Anticipo', compute='get_total_viatic_amount')


    @api.depends('approved_rate', 'qty_person', 'qty_days')
    def get_total_viatic_amount(self):
        for rec in self:
            if rec.approved_rate and rec.qty_person and rec.qty_days:
                rec.sub_total_viatic_amount = rec.approved_rate * rec.qty_person * rec.qty_days
            else:
                rec.sub_total_viatic_amount = 0

    def _prepare_move_lines_vals(self):
        res = super(HrExpense, self)._prepare_move_lines_vals()

        if self.payment_mode == 'viatic':
            viatic_account_id = self.company_id.account_viatic_id
            res['account_id'] = viatic_account_id.id
            res['price_unit'] = self.sub_total_viatic_amount
            res['quantity'] = 1

        return res

    journal_viatic_id = fields.Many2one('account.journal', string='Journal',domain="[('type', '=', 'cash')]", related='company_id.journal_viatic_cash_bank_id')

    def _default_journal_id(self):
        company_id = self.company_id
        if company_id.journal_viatic_cash_bank_id:
            return company_id.journal_viatic_cash_bank_id
        else:
            return False