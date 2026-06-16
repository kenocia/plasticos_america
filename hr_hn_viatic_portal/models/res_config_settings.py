# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_viatic_id = fields.Many2one(
        string="Viatic Account", related='company_id.account_viatic_id', comodel_name='account.account', readonly=False)

    account_viatic_cash_bank_id = fields.Many2one(
        string="Viatic Cash and Bank Account", related='company_id.account_viatic_cash_bank_id',
        comodel_name='account.account', readonly=False)

    journal_viatic_cash_bank_id = fields.Many2one(related='company_id.journal_viatic_cash_bank_id',
                                                         readonly=False)
