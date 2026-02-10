# -*- coding: utf-8 -*-

import datetime
from itertools import chain

from dateutil.relativedelta import relativedelta
from odoo import models, fields
from odoo.tools import SQL


class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    """
    Extiende el engine del reporte de antigüedad (CxC/CxP) para exponer una subfórmula
    adicional: `aging_days`.

    Nota:
    - El handler de CxC (`account.aged.receivable.report.handler`) y el de CxP
      (`account.aged.payable.report.handler`) heredan del handler común
      `account.aged.partner.balance.report.handler`, por lo que este override aplica a ambos.
    """

    _inherit = 'account.aged.partner.balance.report.handler'

    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, next_groupby, offset=0, limit=None):
        res = super()._aged_partner_report_custom_engine_common(
            options, internal_type, current_groupby, next_groupby, offset=offset, limit=limit,
        )

        today = fields.Date.context_today(self)

        def _to_date(value):
            if not value:
                return None
            if isinstance(value, datetime.datetime):
                return value.date()
            if isinstance(value, datetime.date):
                return value
            if isinstance(value, str):
                s = value.strip()
                # Caso típico: 'YYYY-MM-DD' o 'YYYY-MM-DD ...'
                if len(s) >= 10 and s[4:5] == '-' and s[7:8] == '-':
                    try:
                        return fields.Date.from_string(s[:10])
                    except Exception:
                        pass
                # Intento 2: date estricta
                try:
                    return fields.Date.from_string(s)
                except Exception:
                    pass
                # Intento 3: datetime -> date
                try:
                    return fields.Datetime.from_string(s).date()
                except Exception:
                    return None
            return None

        def _inject_date(values, aml_dates=None, aml_id=None):
            date_value = None
            if aml_dates and aml_id:
                date_value = aml_dates.get(aml_id)
            if not date_value:
                date_value = _to_date(values.get('date'))
            if not date_value:
                date_value = _to_date(values.get('due_date'))
            if not date_value:
                date_value = _to_date(values.get('invoice_date'))
            values['date'] = date_value

        def _inject_aging_days(values):
            # Calcula días de antigüedad con base en la fecha contable vs fecha actual.
            aml_date = _to_date(values.get('date'))
            if today and aml_date:
                values['aging_days'] = max(0, (today - aml_date).days)
            else:
                values['aging_days'] = None

        if isinstance(res, dict):
            _inject_date(res)
            _inject_aging_days(res)
            return res

        # Forma estándar cuando hay groupby: lista de tuplas (grouping_key, dict_values)
        if isinstance(res, list):
            aml_ids = [
                grouping_key
                for grouping_key, values in res
                if isinstance(values, dict) and values.get('partner_id')
            ]
            aml_dates = {
                aml.id: aml.date
                for aml in self.env['account.move.line'].browse(aml_ids)
            } if aml_ids else {}
            for grouping_key, values in res:
                if isinstance(values, dict):
                    if values.get('partner_id'):
                        _inject_date(values, aml_dates=aml_dates, aml_id=grouping_key)
                    else:
                        _inject_date(values)
                    _inject_aging_days(values)
            return res

        return res

    def _prepare_partner_values(self):
        values = super()._prepare_partner_values()
        values['date'] = None
        values['aging_days'] = None
        return values


class AgedReceivableCustomHandler(models.AbstractModel):
    _inherit = 'account.aged.receivable.report.handler'

    def _get_custom_display_config(self):
        config = super()._get_custom_display_config()
        pdf_export = dict(config.get('pdf_export', {}))
        pdf_export.update({
            'pdf_export_main_table_body': 'kc_fiscal_hn.aged_receivable_pdf_export_main_table_body',
        })
        config['pdf_export'] = pdf_export
        return config

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        for index, line in enumerate(lines):
            next_line = lines[index + 1] if index + 1 < len(lines) else None
            is_group_end = False
            if line.get('level') == 2:
                if not next_line or next_line.get('level', 0) <= 1:
                    is_group_end = True
            elif line.get('level') == 1 and not line.get('unfolded'):
                if not next_line or next_line.get('level', 0) <= 1:
                    is_group_end = True
            if is_group_end:
                line['is_partner_group_end'] = True
        return lines

    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, next_groupby, offset=0, limit=None):
        report = self.env['account.report'].browse(options['report_id'])
        report._check_groupby_fields((next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        def minus_days(date_obj, days):
            return fields.Date.to_string(date_obj - relativedelta(days=days))

        aging_date_field = SQL.identifier('invoice_date') if options['aging_based_on'] == 'base_on_invoice_date' else SQL.identifier('date_maturity')
        period_date_field = SQL.identifier('date')
        date_to = fields.Date.context_today(self)
        interval = options['aging_interval']
        periods = [(False, fields.Date.to_string(date_to))]
        nb_periods = len([column for column in options['columns'] if column['expression_label'].startswith('period')]) - 1
        for i in range(nb_periods):
            start_date = minus_days(date_to, (interval * i) + 1)
            end_date = minus_days(date_to, interval * (i + 1)) if i < nb_periods - 1 else False
            periods.append((start_date, end_date))

        def _compute_aging_days(date_value):
            if date_to and date_value:
                return max(0, (date_to - date_value).days)
            return None

        def build_result_dict(report, query_res_lines):
            rslt = {f'period{i}': 0 for i in range(len(periods))}

            for query_res in query_res_lines:
                for i in range(len(periods)):
                    period_key = f'period{i}'
                    rslt[period_key] += query_res[period_key]

            if current_groupby == 'id':
                query_res = query_res_lines[0]
                currency = self.env['res.currency'].browse(query_res['currency_id'][0]) if len(query_res['currency_id']) == 1 else None
                aml_date = query_res['aml_date'][0] if len(query_res['aml_date']) == 1 else None
                rslt.update({
                    'invoice_date': query_res['invoice_date'][0] if len(query_res['invoice_date']) == 1 else None,
                    'due_date': query_res['due_date'][0] if len(query_res['due_date']) == 1 else None,
                    'date': aml_date,
                    'aging_days': _compute_aging_days(aml_date),
                    'amount_currency': query_res['amount_currency'],
                    'currency_id': query_res['currency_id'][0] if len(query_res['currency_id']) == 1 else None,
                    'currency': currency.display_name if currency else None,
                    'account_name': query_res['account_name'][0] if len(query_res['account_name']) == 1 else None,
                    'total': None,
                    'has_sublines': query_res['aml_count'] > 0,
                    'partner_id': query_res['partner_id'][0] if query_res['partner_id'] else None,
                })
            else:
                rslt.update({
                    'invoice_date': None,
                    'due_date': None,
                    'date': None,
                    'aging_days': None,
                    'amount_currency': None,
                    'currency_id': None,
                    'currency': None,
                    'account_name': None,
                    'total': sum(rslt[f'period{i}'] for i in range(len(periods))),
                    'has_sublines': False,
                })

            return rslt

        period_table_format = ('(VALUES %s)' % ','.join("(%s, %s, %s)" for period in periods))
        params = list(chain.from_iterable(
            (period[0] or None, period[1] or None, i)
            for i, period in enumerate(periods)
        ))
        period_table = SQL(period_table_format, *params)

        query = report._get_report_query(options, 'strict_range', domain=[('account_id.account_type', '=', internal_type)])
        account_alias = query.left_join(lhs_alias='account_move_line', lhs_column='account_id', rhs_table='account_account', rhs_column='id', link='account_id')
        account_code = self.env['account.account']._field_to_sql(account_alias, 'code', query)

        always_present_groupby = SQL("period_table.period_index")
        if current_groupby:
            select_from_groupby = SQL("%s AS grouping_key,", SQL.identifier("account_move_line", current_groupby))
            groupby_clause = SQL("%s, %s", SQL.identifier("account_move_line", current_groupby), always_present_groupby)
        else:
            select_from_groupby = SQL()
            groupby_clause = always_present_groupby
        multiplicator = -1 if internal_type == 'liability_payable' else 1
        select_period_query = SQL(',').join(
            SQL("""
                CASE WHEN period_table.period_index = %(period_index)s
                THEN %(multiplicator)s * SUM(%(balance_select)s)
                ELSE 0 END AS %(column_name)s
                """,
                period_index=i,
                multiplicator=multiplicator,
                column_name=SQL.identifier(f"period{i}"),
                balance_select=report._currency_table_apply_rate(SQL(
                    "account_move_line.balance - COALESCE(part_debit.amount, 0) + COALESCE(part_credit.amount, 0)"
                )),
            )
            for i in range(len(periods))
        )

        tail_query = report._get_engine_query_tail(offset, limit)
        query = SQL(
            """
            WITH period_table(date_start, date_stop, period_index) AS (%(period_table)s)

            SELECT
                %(select_from_groupby)s
                %(multiplicator)s * (
                    SUM(account_move_line.amount_currency)
                    - COALESCE(SUM(part_debit.debit_amount_currency), 0)
                    + COALESCE(SUM(part_credit.credit_amount_currency), 0)
                ) AS amount_currency,
                ARRAY_AGG(DISTINCT account_move_line.partner_id) AS partner_id,
                ARRAY_AGG(account_move_line.payment_id) AS payment_id,
                ARRAY_AGG(DISTINCT move.invoice_date) AS invoice_date,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date)) AS report_date,
                ARRAY_AGG(DISTINCT account_move_line.date) AS aml_date,
                ARRAY_AGG(DISTINCT %(account_code)s) AS account_name,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.%(aging_date_field)s, account_move_line.date)) AS due_date,
                ARRAY_AGG(DISTINCT account_move_line.currency_id) AS currency_id,
                COUNT(account_move_line.id) AS aml_count,
                ARRAY_AGG(%(account_code)s) AS account_code,
                %(select_period_query)s

            FROM %(table_references)s

            JOIN account_journal journal ON journal.id = account_move_line.journal_id
            JOIN account_move move ON move.id = account_move_line.move_id
            %(currency_table_join)s

            LEFT JOIN LATERAL (
                SELECT
                    SUM(part.amount) AS amount,
                    SUM(part.debit_amount_currency) AS debit_amount_currency,
                    part.debit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date_to)s AND part.debit_move_id = account_move_line.id
                GROUP BY part.debit_move_id
            ) part_debit ON TRUE

            LEFT JOIN LATERAL (
                SELECT
                    SUM(part.amount) AS amount,
                    SUM(part.credit_amount_currency) AS credit_amount_currency,
                    part.credit_move_id
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(date_to)s AND part.credit_move_id = account_move_line.id
                GROUP BY part.credit_move_id
            ) part_credit ON TRUE

            JOIN period_table ON
                (
                    period_table.date_start IS NULL
                    OR COALESCE(account_move_line.%(period_date_field)s, account_move_line.date) <= DATE(period_table.date_start)
                )
                AND
                (
                    period_table.date_stop IS NULL
                    OR COALESCE(account_move_line.%(period_date_field)s, account_move_line.date) >= DATE(period_table.date_stop)
                )

            WHERE %(search_condition)s

            GROUP BY %(groupby_clause)s

            HAVING
                ROUND(SUM(%(having_debit)s), %(currency_precision)s) != 0
                OR ROUND(SUM(%(having_credit)s), %(currency_precision)s) != 0

            ORDER BY %(groupby_clause)s

            %(tail_query)s
            """,
            account_code=account_code,
            period_table=period_table,
            select_from_groupby=select_from_groupby,
            select_period_query=select_period_query,
            multiplicator=multiplicator,
            aging_date_field=aging_date_field,
            period_date_field=period_date_field,
            table_references=query.from_clause,
            currency_table_join=report._currency_table_aml_join(options),
            date_to=date_to,
            search_condition=query.where_clause,
            groupby_clause=groupby_clause,
            having_debit=report._currency_table_apply_rate(SQL("CASE WHEN account_move_line.balance > 0  THEN account_move_line.balance else 0 END - COALESCE(part_debit.amount, 0)")),
            having_credit=report._currency_table_apply_rate(SQL("CASE WHEN account_move_line.balance < 0  THEN -account_move_line.balance else 0 END - COALESCE(part_credit.amount, 0)")),
            currency_precision=self.env.company.currency_id.decimal_places,
            tail_query=tail_query,
        )

        self._cr.execute(query)
        query_res_lines = self._cr.dictfetchall()

        if not current_groupby:
            return build_result_dict(report, query_res_lines)
        else:
            rslt = []

            all_res_per_grouping_key = {}
            for query_res in query_res_lines:
                grouping_key = query_res['grouping_key']
                all_res_per_grouping_key.setdefault(grouping_key, []).append(query_res)

            for grouping_key, query_res_lines in all_res_per_grouping_key.items():
                rslt.append((grouping_key, build_result_dict(report, query_res_lines)))

            return rslt

    def _build_domain_from_period(self, options, period):
        if period != "total" and period[-1].isdigit():
            period_number = int(period[-1])
            interval = options.get('aging_interval', 30)
            options_date_to = fields.Date.context_today(self)
            if period_number == 0:
                domain = [('date', '>=', options_date_to)]
            else:
                period_end = options_date_to - datetime.timedelta(interval * (period_number - 1) + 1)
                period_start = options_date_to - datetime.timedelta(interval * period_number)
                domain = [('date', '>=', period_start), ('date', '<=', period_end)]
                if period_number == 5:
                    domain = [('date', '<=', period_end)]
        else:
            domain = []
        return domain
