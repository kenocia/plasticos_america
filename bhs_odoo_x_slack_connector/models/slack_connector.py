import slack, html
import odoo
from odoo import _, registry, SUPERUSER_ID
import logging
from htmlslacker import HTMLSlacker
from odoo import models, fields, api
from datetime import date
from odoo.tools.misc import clean_context, split_every
import threading

_logger = logging.getLogger(__name__)


class SlackConnector(models.Model):
    _name = 'slack.connector'
    _description = 'Slack connector settings'

    name = fields.Char(string='Name')
    namespace = fields.Selection([('slack','Slack')], string='Namespace')
    workspace_id = fields.Char(string='Workspace ID')
    workspace_name = fields.Char(string='Workspace Name')
    access_token = fields.Char(string='Access Token')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('namespace_workspace_uniq', 'unique (namespace, workspace_id)', "Workspace ID must be unique!"),
    ]

    def send_notification_to_channel(self, channel, text, blocks=None):
        """Envía una notificación a un canal de Slack.

        :param channel: ID del canal o nombre (ej: 'C1234567890' o '#general')
        :param text: Texto del mensaje (usado como fallback si se envían blocks)
        :param blocks: opcional, lista de bloques Block Kit de Slack para formato enriquecido
        :return: respuesta de la API de Slack o False si falla
        """
        self.ensure_one()
        if not self.access_token:
            _logger.warning(_('Slack connector "%s" sin Access Token configurado.') % self.name)
            return False
        try:
            client = slack.WebClient(token=self.access_token)
            if blocks:
                return client.chat_postMessage(channel=channel, text=text, blocks=blocks)
            return client.chat_postMessage(channel=channel, text=text)
        except Exception as e:
            _logger.exception(_('Error enviando notificación a Slack canal %s: %s') % (channel, e))
            return False


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        recipients_data = super(MailThread, self)._notify_thread(message, msg_vals=msg_vals, **kwargs)
        self._notify_record_by_slack(message, recipients_data, msg_vals=msg_vals, **kwargs)
        return recipients_data

    def _notify_record_by_slack(self, message, recipients_data, msg_vals=False, **kwargs):
        _logger.info("_notify_record_by_slack")

        """ Notification method: by SLACK.

        :param message: mail.message record to notify;
        :param recipients_data: see ``_notify_thread``;
        :param msg_vals: see ``_notify_thread``;
        """
        # notify from computed recipients_data (followers, specific recipients)
        partners_data = [r for r in recipients_data if r['notif'] == 'slack']
        partner_ids = [r['id'] for r in partners_data]
        if partner_ids:
            for partner in self.env['res.partner'].sudo().browse(partner_ids):
                user_data = self.env['res.users'].sudo().search([('partner_id','=',partner.id)])
                slack_user_configs = user_data.slack_user_config.filtered(lambda rec: rec.active is True)

                _logger.info("User: %s" % user_data.name)
                _logger.info("Slack_user_configs: %s" % slack_user_configs)
                _logger.info("Message: %s" % message)

                notif = False  # sql constraints on message and partner => create only one notification
                for slack_user_config in slack_user_configs:
                    try:
                        if message.message_type == 'user_notification' or (not message.subtype_id and message.model == 'hr.leave'):
                            text = message.subject
                        else:
                            text = message.body
                        web_base_url = self.env['ir.config_parameter'].sudo().get_param(
                            'web.base.url')  # must be https if not localhost

                        if 'href' in text:
                            text = text.replace('/odoo', web_base_url + '/odoo')
                        text = HTMLSlacker(text).get_output()
                        # link_record = message.action_open_document()

                        link = web_base_url + f'/odoo/{message.model}/{message.res_id}'
                        _logger.info('Model in message: %s' % message.model)
                        # if message.model == 'mail.channel':
                        #     act_mail_channel = self.env['ir.model.data'].sudo().search([('module','=','mail'),('name','=','action_discuss')],limit=1)
                        #     link = web_base_url + '/web#default_active_id=mail.box_inbox&action=%s&active_id=mail.channel_%s' % (act_mail_channel.res_id, message.res_id)

                        text_slack = _(':speech_balloon: *Notification from Odoo*:')
                        # text_slack += _('\n*Loại*:') + dict(message._fields['message_type'].selection).get(message.message_type)
                        model_description = self.env['ir.model'].sudo().search([('model','=',message.model)],limit=1)
                        if model_description:
                            text_slack += _('\n*%s:*') % model_description.name
                        if not text:
                            text = _('*System Notification (%s)*') % (message.subtype_id.name)
                        text_slack += _('\n*Content*: ') + html.unescape(text)

                        if message.author_id:
                            text_slack += _('\n*Author*: ') + message.author_id.name
                        if message.subtype_id:
                            text_slack += _('\n*Subtype*: ') + message.subtype_id.name

                        text_slack += _('\n*Link*: ') + link

                        if slack_user_config.slack_connector.access_token:
                            client = slack.WebClient(token=slack_user_config.slack_connector.access_token)
                            # tin nhắn hệ thống để tracking các trường thay đổi nên không gửi
                            if message.message_type == 'notification':
                                pass
                            # elif message.model == 'hr.leave' and not message.subtype_id:
                            #     pass
                            else:
                                client.chat_postMessage(channel=slack_user_config.member_id, blocks=[
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": text_slack
                                        }
                                    }
                                ])
                        else:
                            # print(text_slack)
                            _logger.exception(_('Not config Slack connector yet.'))
                    except Exception as e:
                        _logger.exception(e)
                        if not notif:
                            notif = self.env['mail.notification'].sudo().create([{
                                'mail_message_id': message.id,
                                'res_partner_id': partner.id,
                                'notification_type': 'slack',
                                'slack_user_config': slack_user_config.id,
                                'is_read': True,  # discard Inbox notification
                                'notification_status': 'sent',
                                'failure_type': 'slack_server',
                                'failure_reason': e
                            }])

                    if not notif:
                        notif = self.env['mail.notification'].sudo().create([{
                            'mail_message_id': message.id,
                            'res_partner_id': partner.id,
                            'notification_type': 'slack',
                            'slack_user_config': slack_user_config.id,
                            'is_read': True,  # discard Inbox notification
                            'notification_status': 'sent'
                        }])

    # Copy all code odoo by Nhat to fix error (delete time off when notification by mail)
    # def _notify_thread_by_email(self, message, recipients_data, msg_vals=False,
    #                             mail_auto_delete=True,  # mail.mail
    #                             model_description=False, force_email_company=False, force_email_lang=False,
    #                             # rendering
    #                             subtitles=None,  # rendering
    #                             resend_existing=False, force_send=True, send_after_commit=True,  # email send
    #                             **kwargs):
    #     """ Method to send emails notifications linked to a message.
    #
    #     :param record message: <mail.message> record being notified. May be
    #       void as 'msg_vals' superseeds it;
    #     :param list recipients_data: list of recipients data based on <res.partner>
    #       records formatted like [
    #       {
    #         'active': partner.active;
    #         'id': id of the res.partner being recipient to notify;
    #         'is_follower': follows the message related document;
    #         'lang': its lang;
    #         'groups': res.group IDs if linked to a user;
    #         'notif': 'inbox', 'email', 'sms' (SMS App);
    #         'share': is partner a customer (partner.partner_share);
    #         'type': partner usage ('customer', 'portal', 'user');
    #         'ushare': are users shared (if users, all users are shared);
    #       }, {...}]. See ``MailThread._notify_get_recipients()``;
    #     :param dict msg_vals: values dict used to create the message, allows to
    #       skip message usage and spare some queries;
    #
    #     :param bool mail_auto_delete: delete notification emails once sent;
    #
    #     :param str model_description: description of current model, given to
    #       avoid fetching it and easing translation support;
    #     :param record force_email_company: <res.company> record used when rendering
    #       notification layout. Otherwise computed based on current record;
    #     :param str force_email_lang: lang used when rendering content, used
    #       notably to compute model name or translate access buttons;
    #     :param list subtitles: optional list set as template value "subtitles";
    #
    #     :param bool resend_existing: check for existing notifications to update
    #       based on mailed recipient, otherwise create new notifications;
    #     :param bool force_send: send emails directly instead of using queue;
    #     :param bool send_after_commit: if force_send, tells to send emails after
    #       the transaction has been committed using a post-commit hook;
    #     """
    #     partners_data = [r for r in recipients_data if r['notif'] == 'email']
    #     if not partners_data:
    #         return True
    #
    #     base_mail_values = self._notify_by_email_get_base_mail_values(
    #         message,
    #         additional_values={'auto_delete': mail_auto_delete}
    #     )
    #
    #     # Clean the context to get rid of residual default_* keys that could cause issues during
    #     # the mail.mail creation.
    #     # Example: 'default_state' would refer to the default state of a previously created record
    #     # from another model that in turns triggers an assignation notification that ends up here.
    #     # This will lead to a traceback when trying to create a mail.mail with this state value that
    #     # doesn't exist.
    #     SafeMail = self.env['mail.mail'].sudo().with_context(clean_context(self._context))
    #     SafeNotification = self.env['mail.notification'].sudo().with_context(clean_context(self._context))
    #     emails = self.env['mail.mail'].sudo()
    #
    #     # loop on groups (customer, portal, user,  ... + model specific like group_sale_salesman)
    #     gen_batch_size = int(
    #         self.env['ir.config_parameter'].sudo().get_param('mail.batch_size')
    #     ) or 50  # be sure to not have 0, as otherwise no iteration is done
    #     notif_create_values = []
    #     for _lang, render_values, recipients_group in self._notify_get_classified_recipients_iterator(
    #             message,
    #             partners_data,
    #             msg_vals=msg_vals,
    #             model_description=model_description,
    #             force_email_company=force_email_company,
    #             force_email_lang=force_email_lang,
    #             subtitles=subtitles,
    #     ):
    #         # generate notification email content
    #         mail_body = self._notify_by_email_render_layout(
    #             message,
    #             recipients_group,
    #             msg_vals=msg_vals,
    #             render_values=render_values,
    #         )
    #         recipients_ids = recipients_group.pop('recipients')
    #
    #         # create email
    #         for recipients_ids_chunk in split_every(gen_batch_size, recipients_ids):
    #             mail_values = self._notify_by_email_get_final_mail_values(
    #                 recipients_ids_chunk,
    #                 base_mail_values,
    #                 additional_values={'body_html': mail_body}
    #             )
    #             new_email = SafeMail.create(mail_values)
    #
    #             if new_email and recipients_ids_chunk:
    #                 tocreate_recipient_ids = list(recipients_ids_chunk)
    #                 if resend_existing:
    #                     existing_notifications = self.env['mail.notification'].sudo().search([
    #                         ('mail_message_id', '=', message.id),
    #                         ('notification_type', '=', 'email'),
    #                         ('res_partner_id', 'in', tocreate_recipient_ids)
    #                     ])
    #                     if existing_notifications:
    #                         tocreate_recipient_ids = [rid for rid in recipients_ids_chunk if
    #                                                   rid not in existing_notifications.mapped('res_partner_id.id')]
    #                         existing_notifications.write({
    #                             'notification_status': 'ready',
    #                             'mail_mail_id': new_email.id,
    #                         })
    #                 notif_create_values += [{
    #                     'author_id': message.author_id.id,
    #                     'is_read': True,  # discard Inbox notification
    #                     'mail_mail_id': new_email.id,
    #                     'mail_message_id': message.id,
    #                     'notification_status': 'ready',
    #                     'notification_type': 'email',
    #                     'res_partner_id': recipient_id,
    #                 } for recipient_id in tocreate_recipient_ids]
    #             emails += new_email
    #
    #     if notif_create_values:
    #         SafeNotification.create(notif_create_values)
    #
    #     # NOTE:
    #     #   1. for more than 50 followers, use the queue system
    #     #   2. do not send emails immediately if the registry is not loaded,
    #     #      to prevent sending email during a simple update of the database
    #     #      using the command-line.
    #     test_mode = getattr(threading.current_thread(), 'testing', False)
    #     if force_send := self.env.context.get('mail_notify_force_send', force_send):
    #         force_send_limit = int(
    #             self.env['ir.config_parameter'].sudo().get_param('mail.mail.force.send.limit', 100))
    #         force_send = len(emails) < force_send_limit
    #     if force_send and (not self.pool._init or test_mode):
    #         # unless asked specifically, send emails after the transaction to
    #         # avoid side effects due to emails being sent while the transaction fails
    #         if not test_mode and send_after_commit:
    #             email_ids = emails.ids
    #             dbname = self.env.cr.dbname
    #             _context = self._context
    #
    #             @self.env.cr.postcommit.add
    #             def send_notifications():
    #                 db_registry = registry(dbname)
    #                 with db_registry.cursor() as cr:
    #                     env = api.Environment(cr, SUPERUSER_ID, _context)
    #                     # env['mail.mail'].browse(email_ids).send()
    #                     # error because email_id was deleted
    #                     for email_id in email_ids:
    #                         check_email = env['mail.mail'].search([('id', '=', email_id)])
    #                         if check_email:
    #                             check_email.send()
    #         else:
    #             emails.send()
    #
    #     return True