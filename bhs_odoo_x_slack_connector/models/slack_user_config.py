from odoo import models, fields, api
from datetime import date


# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, exceptions, fields, models, modules
from odoo.addons.base.models.res_users import is_selection_groups

class SlackUserConfig(models.Model):
    _name = 'slack.user.config'
    _description = 'Slack User Config'
    _rec_name = "slack_connector"

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade')
    slack_connector = fields.Many2one('slack.connector', string='Slack Connector')
    member_id = fields.Char(string='Member ID')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('slack_connector_user_uniq', 'unique (slack_connector, user_id)', "User already exists in this Slack connector!"),
    ]

class Users(models.Model):
    """ Update of res.users class
        - add option Handle by Slack for notification type.
    """
    _inherit = 'res.users'

    # notification_type = fields.Selection(
    #     [('email', 'Handle by Emails'), ('inbox', 'Handle in Odoo'), ('slack', 'Handle by Slack')],
    #     help="Policy on how to handle Chatter notifications:\n"
    #          "- Handle by Emails: notifications are sent to your email address\n"
    #          "- Handle in Odoo: notifications appear in your Odoo Inbox\n"
    #          "- Handle by Slack: notifications are sent to Workspace on Slack"
    # )
    notification_type = fields.Selection(selection_add=[('slack', 'Handle by Slack')], ondelete={'slack': 'cascade'},
        help="Policy on how to handle Chatter notifications:\n"
             "- Handle by Emails: notifications are sent to your email address\n"
             "- Handle in Odoo: notifications appear in your Odoo Inbox\n"
             "- Handle by Slack: notifications are sent to Workspace on Slack"
    )
    slack_user_config = fields.One2many('slack.user.config', 'user_id', string='Slack User Config')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['slack_user_config']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['slack_user_config']

    def write(self, vals):
        res = super(Users, self).write(vals)
        if 'active' in vals:
            slack_configs = self.with_context(active_test=False).mapped('slack_user_config')
            slack_configs.write({'active': vals['active']})
        return res
