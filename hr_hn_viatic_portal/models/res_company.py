# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = "res.company"
    account_viatic_id = fields.Many2one(comodel_name='account.account', string="Viatic Account", domain="[('account_type', '=', 'asset_current'), ('reconcile','=', True)]")

    account_viatic_cash_bank_id = fields.Many2one(comodel_name='account.account',string="Viatic Cash and Bank Account",
                                                  domain="[('account_type', '=', 'asset_cash')]")

    journal_viatic_cash_bank_id = fields.Many2one(
        comodel_name='account.journal',
        string='Viatic Cash Account Journal',
        domain=[('type', '=', 'cash')],
    )