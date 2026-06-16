# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    slack_client_id = fields.Char(string="Slack Client ID")
    slack_client_secret = fields.Char(string="Slack Client Secret")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        slack_client_id = self.env['ir.config_parameter'].sudo().get_param('slack_client_id') or False
        slack_client_secret = self.env['ir.config_parameter'].sudo().get_param('slack_client_secret') or False
        res.update({
            'slack_client_id': slack_client_id,
            'slack_client_secret': slack_client_secret,
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param("slack_client_id", self.slack_client_id)
        self.env['ir.config_parameter'].sudo().set_param("slack_client_secret", self.slack_client_secret)
