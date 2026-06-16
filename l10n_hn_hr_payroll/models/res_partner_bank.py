# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class ResBank(models.Model):
    _name = 'res.bank'
    _inherit = 'res.bank'

    bank_sequence = fields.Many2one('ir.sequence', string='Bank Sequence', readonly=True)
    sequence_init = fields.Integer(string='Sequence Start', default=1)

    @api.model
    def create(self, vals):
        if 'sequence_init' in vals:
            sequence = self.env['ir.sequence'].create({
                'name': vals.get('name') + ' Sequence',
                'code': vals.get('name').lower().replace(" ", ".") + '.sequence',
                'implementation': 'no_gap',
                'prefix': "",
                'padding': 5,
                'number_next': vals.get('sequence_init', 1),
            })
            vals['bank_sequence'] = sequence.id
        return super(ResBank, self).create(vals)

    def assign_sequence(self):
        for bank in self:
            if not bank.bank_sequence:
                sequence = self.env['ir.sequence'].create({
                    'name': bank.name + ' Sequence',
                    'code': bank.name .lower().replace(" ", ".") + '.sequence',
                    'implementation': 'no_gap',
                    'prefix': "",
                    'padding': 5,
                    'number_next': bank.sequence_init,
                })
                bank.bank_sequence = sequence.id