# -*- coding: utf-8 -*-
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bch_api_key = fields.Char(
        string="BCH API Key",
        config_parameter='kc_currency_rate_bch.api_key',
    )
    bch_indicator_id = fields.Integer(
        string="BCH Indicator ID",
        default=97,
        config_parameter='kc_currency_rate_bch.indicator_id',
    )
    bch_currency_code = fields.Char(
        string="Currency Code",
        default='USD',
        config_parameter='kc_currency_rate_bch.currency_code',
    )
    bch_company_currency_code = fields.Char(
        string="Company Currency Code",
        default='HNL',
        config_parameter='kc_currency_rate_bch.company_currency_code',
    )


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _cron_update_bch_rates(self):
        _logger.info("KC BCH: Starting rate update.")
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('kc_currency_rate_bch.api_key')
        if not api_key:
            _logger.warning("KC BCH: API key not configured.")
            return False

        indicator_id = params.get_param('kc_currency_rate_bch.indicator_id', '97')
        currency_code = params.get_param('kc_currency_rate_bch.currency_code', 'USD')
        company_currency_code = params.get_param('kc_currency_rate_bch.company_currency_code', 'HNL')
        _logger.info(
            "KC BCH: Config indicator=%s currency=%s company_currency=%s.",
            indicator_id,
            currency_code,
            company_currency_code,
        )

        try:
            indicator_id = int(indicator_id)
        except (TypeError, ValueError):
            indicator_id = 97

        url = "https://bchapi-am.azure-api.net/api/v1/indicadores/%s/cifras?formato=Json" % indicator_id
        headers = {
            'clave': api_key,
            'Accept': 'application/json',
        }
        _logger.info("KC BCH: Fetching BCH data from %s.", url)

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            _logger.exception("KC BCH: Error fetching BCH rate: %s", exc)
            return False

        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict) and payload.get('data'):
            items = payload.get('data', [])

        if not items:
            _logger.warning("KC BCH: No data returned by BCH API.")
            return False
        _logger.info("KC BCH: %s items received from BCH API.", len(items))

        latest = max(items, key=lambda item: item.get('Fecha') or '')
        rate_value = latest.get('Valor')
        if rate_value in (None, ''):
            _logger.warning("KC BCH: No rate value found in BCH response.")
            return False

        try:
            rate_value = float(rate_value)
        except (TypeError, ValueError):
            _logger.warning("KC BCH: Invalid rate value: %s", rate_value)
            return False

        rate_date = fields.Date.context_today(self)
        if latest.get('Fecha'):
            try:
                rate_date = fields.Date.to_date(latest.get('Fecha'))
            except Exception:
                _logger.warning("KC BCH: Invalid date in BCH response: %s", latest.get('Fecha'))

        currency = self.env['res.currency'].sudo().search([('name', '=', currency_code)], limit=1)
        if not currency:
            _logger.warning("KC BCH: Currency %s not found.", currency_code)
            return False
        _logger.info("KC BCH: Target currency found: %s.", currency.name)

        companies = self.env['res.company'].sudo().search([])
        updated_companies = 0
        for company in companies:
            if company_currency_code and company.currency_id.name != company_currency_code:
                continue

            rate = self.env['res.currency.rate'].sudo().search([
                ('currency_id', '=', currency.id),
                ('company_id', '=', company.id),
                ('name', '=', rate_date),
            ], limit=1)

            if rate:
                rate.rate = rate_value
            else:
                self.env['res.currency.rate'].sudo().create({
                    'currency_id': currency.id,
                    'company_id': company.id,
                    'name': rate_date,
                    'rate': rate_value,
                })
            updated_companies += 1

        _logger.info(
            "KC BCH: Rate updated for %s on %s. Companies updated: %s.",
            currency_code,
            rate_date,
            updated_companies,
        )
        return True

    def action_update_bch_rate(self):
        success = self._cron_update_bch_rates()
        if success:
            message = "Tipo de cambio BCH actualizado correctamente."
            notif_type = "success"
        else:
            message = "No se pudo actualizar el tipo de cambio BCH. Revisa la configuración y los logs."
            notif_type = "warning"
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "BCH",
                'message': message,
                'type': notif_type,
                'sticky': False,
            }
        }
