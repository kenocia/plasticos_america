# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    notification_type = fields.Selection(selection_add=[('slack', 'Slack')], ondelete={'slack': 'cascade'})
    slack_user_config = fields.Many2one('slack.user.config', string='Slack user config', index=True)
    failure_type = fields.Selection(selection_add=[('slack_server', 'Server Error')])
