# -*- coding: utf-8 -*-
######################################################################################
#

#
########################################################################################
import re
from datetime import datetime, timedelta
from odoo import models, api
from odoo.exceptions import UserError
from odoo.tools import email_split
from odoo import fields, models, tools, api, _
from dateutil import rrule, relativedelta


class HrLeave(models.Model):
    _name = "hr.leave"
    _inherit = ['hr.leave', 'portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']

    def _compute_access_url(self):
        # super(PyS self)._compute_access_url()
        for leave in self:
            leave.access_url = '/my/leaves/%s' % (leave.id)

    def _get_portal_return_action(self):
        """ Return the action used to display leave. """
        self.ensure_one()
        return self.env.ref('sale.action_quotations_with_onboarding')

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s' % self.name

    # @api.returns('mail.message', lambda value: value.id)
    # def message_post(self, **kwargs):
    #     if self.env.context.get('mark_so_as_sent'):
    #         self.filtered(lambda o: o.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
    #     if 'author_id' in kwargs:
    #         author_id = kwargs['author_id']
    #         channel_info = self.env['mail.channel'].channel_get([author_id])
    #         if self.name:
    #             message = kwargs['body'] + "Petición de ausencia=" + self.name
    #         else:
    #             message = kwargs['body'] + "Petición de ausencia="
    #
    #         self.env['mail.thread'].sudo().message_notify(
    #             body=message,
    #             partner_ids=author_id,
    #             subject=_('Your Time Off'),
    #         )
    #         # channel = self.env['mail.channel'].browse(channel_info['id'])
    #         # if self.name:
    #         #     message = kwargs['body'] + "Petición de ausencia=" + self.name
    #         # else:
    #         #     message = kwargs['body'] + "Petición de ausencia="
    #         # channel.sudo().message_post(body=message, author_id=author_id, message_type="comment",
    #         #                             subtype_xmlid="mail.mt_comment")
    #     return super(HrLeave, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    def _get_number_of_days(self, date_from, date_to, employee_id):
        """ Returns a float equals to the timedelta between two dates given as string."""
        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            result = employee._get_work_days_data_batch(date_from, date_to, True, employee.resource_calendar_id)[employee.id]
            if self.request_unit_half:
                result['days'] = 0.5
            return result
