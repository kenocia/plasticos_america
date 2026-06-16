from odoo import models, fields, api, _
from odoo.api import ondelete
from odoo.exceptions import UserError
from odoo.tools.misc import frozendict

class AccountMove(models.Model):
    _inherit = "account.move"

    expense_viatic_sheet_id = fields.Many2one(
    comodel_name='hr.expense.sheet',
    ondelete='cascade',  # Elimina los movimientos cuando se elimina la hoja de viáticos
    copy=False,
    index='btree_not_null')

    def action_open_viatic_expense_report(self):
        self.ensure_one()
        return {
            'name': self.expense_viatic_sheet_id.name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_model': 'hr.expense.sheet',
            'res_id': self.expense_viatic_sheet_id.id
        }

    # Expenses can be written on journal other than purchase, hence don't include them in the constraint check
    def _check_journal_move_type(self):
        return super(AccountMove, self.filtered(lambda x: not x.expense_viatic_sheet_id))._check_journal_move_type()

    def _creation_message(self):
        if self.expense_viatic_sheet_id:
            return _("Expense entry created from: %s", self.expense_viatic_sheet_id._get_html_link())
        return super()._creation_message()

    @api.depends('expense_viatic_sheet_id')
    def _compute_needed_terms(self):
        # EXTENDS account
        # We want to set the account destination based on the 'payment_mode'.
        super()._compute_needed_terms()
        for move in self:
            if move.expense_viatic_sheet_id and move.expense_viatic_sheet_id.payment_mode == 'company_account':
                term_lines = move.line_ids.filtered(lambda l: l.display_type != 'payment_term')
                move.needed_terms = {
                    frozendict(
                        {
                            "move_id": move.id,
                            "date_maturity": move.expense_viatic_sheet_id.accounting_date or fields.Date.context_today(move.expense_viatic_sheet_id),
                        }
                    ): {
                        "balance": -sum(term_lines.mapped("balance")),
                        "amount_currency": -sum(term_lines.mapped("amount_currency")),
                        "name": "",
                        "account_id": move.expense_viatic_sheet_id._get_expense_account_destination(),
                    }
                }

    def _reverse_moves(self, default_values_list=None, cancel=False):
        own_expense_moves = self.filtered(lambda move: move.expense_viatic_sheet_id.payment_mode == 'own_account')
        own_expense_moves.write({'expense_viatic_sheet_id': False, 'ref': False})
        # else, when restarting the expense flow we get duplicate issue on vendor.bill
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    @ondelete(at_uninstall=True)
    def _must_delete_all_expense_entries(self):
        if self.expense_viatic_sheet_id and self.expense_viatic_sheet_id.account_move_ids - self:  # If not all the payments are to be deleted
            raise UserError(_("You cannot delete only some entries linked to an expense report. All entries must be deleted at the same time."))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    def create(self, vals_list):
        for rec in vals_list:
            if self.env.context.get('viatic'):
                if rec.get('display_type') == 'payment_term':
                    rec['display_type'] = 'product'
                    rec['account_id'] = self.env.company.journal_viatic_cash_bank_id.default_account_id.id
                    rec['credit'] = rec['amount_currency']
                    rec['debit'] = 0

                elif rec.get('display_type') == 'product':
                    rec['account_id'] = self.company_id.account_viatic_id.id
        res = super(AccountMoveLine, self).create(vals_list)
        cont = 0
        if self.env.context.get('viatic'):
            for r in res:
                if r.account_id.id == self.env.company.journal_viatic_cash_bank_id.default_account_id.id:
                    r.write({
                        'credit': vals_list[cont]['credit'],
                        'balance': vals_list[cont]['balance'],
                        'debit': vals_list[cont]['debit'],
                    })
                cont = cont + 1
        return res
