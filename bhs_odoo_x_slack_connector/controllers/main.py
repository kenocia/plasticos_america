# -*- coding: utf-8 -*-
import requests
import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SlackAuthentication(http.Controller):
    @http.route('/slack', type='http', auth='public', website=False, sitemap=False)
    def get_authentication(self, **kw):
        code = kw.get('code')
        if not code:
            raise UserError("Slack no envió el parámetro 'code'. Inicia la instalación desde Slack (Install to Workspace).")

        client_id = request.env['ir.config_parameter'].sudo().get_param('slack_client_id')
        client_secret = request.env['ir.config_parameter'].sudo().get_param('slack_client_secret')
        if not client_id or not client_secret:
            raise UserError("Falta configurar Slack Client ID / Slack Client Secret en Odoo.")

        headers = {'content-type': "application/x-www-form-urlencoded"}
        body = {'code': code, 'client_id': client_id, 'client_secret': client_secret}

        r = requests.post("https://slack.com/api/oauth.v2.access", headers=headers, data=body, timeout=30)
        result_data = r.json()

        if not result_data.get('ok'):
            _logger.error("Slack OAuth error: %s", result_data)
            raise UserError("Slack OAuth falló: %s" % (result_data.get('error') or result_data))

        access_token = result_data.get('access_token')
        team = result_data.get('team') or {}
        workspace_id = team.get('id')
        workspace_name = team.get('name')

        if not access_token or not workspace_id:
            _logger.error("Slack OAuth respuesta incompleta: %s", result_data)
            raise UserError("Slack OAuth devolvió datos incompletos.")

        connector = request.env['slack.connector'].sudo().search([
            ('namespace', '=', 'slack'),
            ('workspace_id', '=', workspace_id)
        ], limit=1)

        vals = {
            'name': 'Slack: %s' % (workspace_name or workspace_id),
            'namespace': 'slack',
            'workspace_id': workspace_id,
            'workspace_name': workspace_name,
            'access_token': access_token,
            'active': True,
        }

        if connector:
            connector.write(vals)
        else:
            request.env['slack.connector'].sudo().create(vals)

        _logger.info("Slack conectado. Workspace=%s (%s)", workspace_name, workspace_id)

        # ✅ IMPORTANTÍSIMO: redirigir a Odoo
        return request.redirect('/web')
