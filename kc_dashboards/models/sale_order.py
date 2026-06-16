# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @api.model
    def _kc_dashboard_default_date(self):
        return fields.Date.context_today(self)

    @api.model
    def _kc_dashboard_parse_date(self, date_value):
        if isinstance(date_value, str):
            return fields.Date.from_string(date_value)
        return date_value

    @api.model
    def _kc_dashboard_day_bounds(self, date_value):
        date_value = self._kc_dashboard_parse_date(date_value)
        return (
            fields.Datetime.to_string(datetime.combine(date_value, time.min)),
            fields.Datetime.to_string(datetime.combine(date_value, time.max)),
        )

    @api.model
    def _kc_dashboard_date_range(self, filters):
        today = self._kc_dashboard_default_date()
        date_from = filters.get('date_from') or filters.get('date') or today
        date_to = filters.get('date_to') or filters.get('date') or date_from
        date_from = self._kc_dashboard_parse_date(date_from)
        date_to = self._kc_dashboard_parse_date(date_to)
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from, date_to

    @api.model
    def _kc_dashboard_range_bounds(self, date_from, date_to):
        date_start, _ = self._kc_dashboard_day_bounds(date_from)
        _, date_end = self._kc_dashboard_day_bounds(date_to)
        return date_start, date_end

    @api.model
    def _kc_dashboard_previous_range(self, date_from, date_to):
        days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        return prev_from, prev_to

    @api.model
    def _kc_dashboard_base_domain(self, filters):
        date_from, date_to = self._kc_dashboard_date_range(filters)
        date_start, date_end = self._kc_dashboard_range_bounds(date_from, date_to)
        domain = [
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_end),
        ]
        if filters.get('partner_id'):
            domain.append(('partner_id', '=', int(filters['partner_id'])))
        if filters.get('user_id'):
            domain.append(('user_id', '=', int(filters['user_id'])))
        if filters.get('warehouse_id'):
            domain.append(('warehouse_id', '=', int(filters['warehouse_id'])))
        return domain

    @api.model
    def _kc_is_immediate_payment(self, payment_term):
        if not payment_term:
            return True
        lines = payment_term.line_ids
        if not lines:
            return True
        return all(line.nb_days == 0 for line in lines)

    @api.model
    def _kc_order_payment_label(self, order):
        return 'cash' if self._kc_is_immediate_payment(order.payment_term_id) else 'credit'

    @api.model
    def _kc_format_amount(self, amount, currency):
        return {
            'raw': amount,
            'formatted': f"{currency.symbol} {amount:,.2f}" if currency.position == 'before'
            else f"{amount:,.2f} {currency.symbol}",
        }

    @api.model
    def _kc_get_order_invoices(self, orders):
        return orders.invoice_ids.filtered(
            lambda move: move.move_type == 'out_invoice' and move.state != 'cancel'
        )

    @api.model
    def _kc_count_order_invoices(self, orders):
        return len(set(self._kc_get_order_invoices(orders).ids))

    @api.model
    def _kc_get_dashboard_invoices(self, filters):
        date_from, date_to = self._kc_dashboard_date_range(filters)
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]
        if filters.get('partner_id'):
            domain.append(('partner_id', '=', int(filters['partner_id'])))
        if filters.get('user_id'):
            domain.append(('invoice_user_id', '=', int(filters['user_id'])))
        invoices = self.env['account.move'].search(domain)
        if filters.get('warehouse_id'):
            warehouse_id = int(filters['warehouse_id'])
            invoices = invoices.filtered(
                lambda inv: any(
                    sale_line.order_id.warehouse_id.id == warehouse_id
                    for line in inv.invoice_line_ids
                    for sale_line in line.sale_line_ids
                )
            )
        return invoices

    @api.model
    def _kc_dashboard_company_info(self):
        company = self.env.company
        return {'id': company.id, 'name': company.name}

    @api.model
    def _kc_compute_kpis(self, orders, previous_orders, currency, invoices=None, previous_invoices=None):
        def _order_metrics(records):
            total = sum(records.mapped('amount_total'))
            partners = len(set(records.mapped('partner_id').ids))
            return total, partners

        _, partners = _order_metrics(orders)
        _, prev_partners = _order_metrics(previous_orders)

        if invoices is not None:
            sales_total = sum(invoices.mapped('amount_total'))
            prev_sales_total = sum(previous_invoices.mapped('amount_total')) if previous_invoices else 0.0
        else:
            sales_total, _ = _order_metrics(orders)
            prev_sales_total, _ = _order_metrics(previous_orders)

        invoice_count = self._kc_count_order_invoices(orders)
        prev_invoice_count = self._kc_count_order_invoices(previous_orders)
        invoiced_orders = orders.filtered(lambda o: o.invoice_status == 'invoiced')
        non_invoiced_orders = orders.filtered(lambda o: o.invoice_status != 'invoiced')
        invoiced_count = len(invoiced_orders)
        non_invoiced_count = len(non_invoiced_orders)

        def _delta(current, previous):
            if not previous:
                return 100.0 if current else 0.0
            return ((current - previous) / previous) * 100.0

        return {
            'sales': {
                'value': self._kc_format_amount(sales_total, currency),
                'previous': self._kc_format_amount(prev_sales_total, currency),
                'delta_pct': round(_delta(sales_total, prev_sales_total), 1),
            },
            'customers': {
                'value': partners,
                'previous': prev_partners,
                'delta_pct': round(_delta(partners, prev_partners), 1),
            },
            'orders': {
                'value': invoice_count,
                'previous': prev_invoice_count,
                'delta_pct': round(_delta(invoice_count, prev_invoice_count), 1),
            },
            'invoiced_orders': {
                'value': invoiced_count,
                'invoiced': invoiced_count,
                'non_invoiced': non_invoiced_count,
                'previous': non_invoiced_count,
                'delta_pct': round(_delta(invoiced_count, non_invoiced_count), 1),
            },
        }

    @api.model
    def _kc_order_invoice_label(self, order):
        invoices = self._kc_get_order_invoices(order)
        if not invoices:
            return '-'
        return ', '.join(invoices.mapped('name'))

    @api.model
    def _kc_sales_period_label(self, date_from, date_to, single_label, period_label):
        days = (date_to - date_from).days + 1
        return single_label if days == 1 else period_label

    @api.model
    def _kc_top_customers_data(self, invoices, currency, date_from, date_to):
        top_customers_map = defaultdict(lambda: {'partner_id': 0, 'name': '', 'amount': 0.0})
        for invoice in invoices:
            partner = invoice.partner_id
            entry = top_customers_map[partner.id]
            entry['partner_id'] = partner.id
            entry['name'] = partner.display_name
            entry['amount'] += invoice.amount_total

        top_customers = sorted(top_customers_map.values(), key=lambda x: x['amount'], reverse=True)[:5]
        max_customer_amount = top_customers[0]['amount'] if top_customers else 0.0
        for item in top_customers:
            item['amount_fmt'] = self._kc_format_amount(item['amount'], currency)['formatted']
            item['pct'] = (item['amount'] / max_customer_amount * 100.0) if max_customer_amount else 0.0

        return {
            'title': self._kc_sales_period_label(
                date_from,
                date_to,
                _('Top clientes del día'),
                _('Top clientes del período'),
            ),
            'items': top_customers,
        }

    @api.model
    def _kc_sales_trend_data(self, orders, date_from, date_to, currency):
        days = (date_to - date_from).days + 1
        if days == 1:
            granularity = 'hour'
            title = _('Ventas por hora')
            info = _('Ventas del día agrupadas por hora de confirmación')
        elif days <= 31:
            granularity = 'day'
            title = _('Tendencia de ventas por día')
            info = _('Ventas del período agrupadas por día')
        elif days <= 120:
            granularity = 'week'
            title = _('Tendencia de ventas por semana')
            info = _('Ventas del período agrupadas por semana')
        else:
            granularity = 'month'
            title = _('Tendencia de ventas por mes')
            info = _('Ventas del período agrupadas por mes')

        amounts_map = defaultdict(float)
        for order in orders:
            local_dt = fields.Datetime.context_timestamp(self, order.date_order)
            if granularity == 'hour':
                bucket_key = str(local_dt.hour)
            elif granularity == 'day':
                bucket_key = fields.Date.to_string(local_dt.date())
            elif granularity == 'week':
                week_start = local_dt.date() - timedelta(days=local_dt.weekday())
                bucket_key = fields.Date.to_string(week_start)
            else:
                bucket_key = f'{local_dt.year}-{local_dt.month:02d}'
            amounts_map[bucket_key] += order.amount_total

        points = []
        if granularity == 'hour':
            for hour in range(7, 19):
                bucket_key = str(hour)
                amount = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': f'{hour:02d}:00',
                    'amount': amount,
                    'amount_fmt': self._kc_format_amount(amount, currency)['formatted'],
                })
        elif granularity == 'day':
            current = date_from
            while current <= date_to:
                bucket_key = fields.Date.to_string(current)
                amount = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%d/%m'),
                    'amount': amount,
                    'amount_fmt': self._kc_format_amount(amount, currency)['formatted'],
                })
                current += timedelta(days=1)
        elif granularity == 'week':
            current = date_from - timedelta(days=date_from.weekday())
            while current <= date_to:
                bucket_key = fields.Date.to_string(current)
                amount = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%d/%m'),
                    'amount': amount,
                    'amount_fmt': self._kc_format_amount(amount, currency)['formatted'],
                })
                current += timedelta(days=7)
        else:
            current = date_from.replace(day=1)
            while current <= date_to:
                bucket_key = f'{current.year}-{current.month:02d}'
                amount = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%b %Y'),
                    'amount': amount,
                    'amount_fmt': self._kc_format_amount(amount, currency)['formatted'],
                })
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        max_amount = max((point['amount'] for point in points), default=0.0)
        for point in points:
            point['pct'] = (point['amount'] / max_amount * 100.0) if max_amount else 0.0

        return {
            'granularity': granularity,
            'title': title,
            'info': info,
            'points': points,
        }

    @api.model
    def _kc_sales_trend_drilldown_orders(self, orders, granularity, key):
        if granularity == 'hour':
            hour = int(key)
            return orders.filtered(
                lambda order: fields.Datetime.context_timestamp(self, order.date_order).hour == hour
            )

        if granularity == 'day':
            day_start, day_end = self._kc_dashboard_day_bounds(fields.Date.from_string(key))
            return orders.filtered(
                lambda order: order.date_order >= day_start and order.date_order <= day_end
            )

        if granularity == 'week':
            week_start = fields.Date.from_string(key)
            week_end = week_start + timedelta(days=6)
            range_start, range_end = self._kc_dashboard_range_bounds(week_start, week_end)
            return orders.filtered(
                lambda order: order.date_order >= range_start and order.date_order <= range_end
            )

        year, month = map(int, key.split('-'))
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, 12, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        range_start, range_end = self._kc_dashboard_range_bounds(month_start, month_end)
        return orders.filtered(
            lambda order: order.date_order >= range_start and order.date_order <= range_end
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @api.model
    def get_sales_dashboard_filter_options(self):
        return {}

    @api.model
    def search_sales_dashboard_partners(self, query='', limit=30):
        query = (query or '').strip()
        limit = min(max(int(limit or 30), 1), 50)
        partner_ids = self.search([
            ('state', 'in', ['sale', 'done']),
        ]).mapped('partner_id').ids
        domain = [('id', 'in', partner_ids or [0])]
        if query:
            domain = expression.AND([
                domain,
                ['|', ('name', 'ilike', query), ('vat', 'ilike', query)],
            ])
        partners = self.env['res.partner'].search(domain, limit=limit, order='name')
        return [{'id': partner.id, 'name': partner.display_name} for partner in partners]

    @api.model
    def get_sales_dashboard_data(self, filters=None, page=1, page_size=8):
        filters = filters or {}
        page = max(int(page or 1), 1)
        page_size = max(int(page_size or 8), 1)

        date_from, date_to = self._kc_dashboard_date_range(filters)
        prev_from, prev_to = self._kc_dashboard_previous_range(date_from, date_to)

        domain = self._kc_dashboard_base_domain(filters)
        orders = self.search(domain, order='date_order desc')
        previous_filters = dict(filters)
        previous_filters.update({
            'date_from': fields.Date.to_string(prev_from),
            'date_to': fields.Date.to_string(prev_to),
        })
        previous_filters.pop('date', None)
        previous_orders = self.search(self._kc_dashboard_base_domain(previous_filters))
        invoices = self._kc_get_dashboard_invoices(filters)
        previous_invoices = self._kc_get_dashboard_invoices(previous_filters)

        currency = self.env.company.currency_id
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())

        sales_trend = self._kc_sales_trend_data(orders, date_from, date_to, currency)

        top_customers = self._kc_top_customers_data(invoices, currency, date_from, date_to)

        channel_map = defaultdict(lambda: {'team_id': 0, 'name': _('Sin canal'), 'amount': 0.0})
        for order in orders:
            team = order.team_id
            key = team.id if team else 0
            entry = channel_map[key]
            entry['team_id'] = key
            entry['name'] = team.name if team else _('Sin canal')
            entry['amount'] += order.amount_total

        total_sales = sum(orders.mapped('amount_total'))
        sales_by_channel = sorted(channel_map.values(), key=lambda x: x['amount'], reverse=True)
        for item in sales_by_channel:
            item['amount_fmt'] = self._kc_format_amount(item['amount'], currency)['formatted']
            item['pct'] = (item['amount'] / total_sales * 100.0) if total_sales else 0.0

        cash_amount = sum(o.amount_total for o in orders if self._kc_order_payment_label(o) == 'cash')
        credit_amount = sum(o.amount_total for o in orders if self._kc_order_payment_label(o) == 'credit')
        payment_total = cash_amount + credit_amount
        cash_vs_credit = [
            {
                'key': 'cash',
                'label': _('Contado'),
                'amount': cash_amount,
                'amount_fmt': self._kc_format_amount(cash_amount, currency)['formatted'],
                'pct': (cash_amount / payment_total * 100.0) if payment_total else 0.0,
            },
            {
                'key': 'credit',
                'label': _('Crédito'),
                'amount': credit_amount,
                'amount_fmt': self._kc_format_amount(credit_amount, currency)['formatted'],
                'pct': (credit_amount / payment_total * 100.0) if payment_total else 0.0,
            },
        ]

        total_count = len(orders)
        offset = (page - 1) * page_size
        page_orders = orders[offset:offset + page_size]
        order_lines = []
        for order in page_orders:
            payment_key = self._kc_order_payment_label(order)
            local_dt = fields.Datetime.context_timestamp(self, order.date_order)
            order_lines.append({
                'id': order.id,
                'datetime': local_dt.strftime('%d/%m/%Y %H:%M'),
                'name': order.name,
                'invoice': self._kc_order_invoice_label(order),
                'partner': order.partner_id.display_name,
                'user': order.user_id.name or '-',
                'amount': order.amount_total,
                'amount_fmt': self._kc_format_amount(order.amount_total, currency)['formatted'],
                'status': _('Pagada') if payment_key == 'cash' else _('Crédito'),
                'status_key': payment_key,
            })

        return {
            'title': _('Ventas'),
            'company': self._kc_dashboard_company_info(),
            'updated_at': now.strftime('%I:%M %p').replace('AM', 'a. m.').replace('PM', 'p. m.'),
            'currency': {
                'symbol': currency.symbol,
                'position': currency.position,
            },
            'filters': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'previous_date_from': fields.Date.to_string(prev_from),
                'previous_date_to': fields.Date.to_string(prev_to),
                'partner_id': filters.get('partner_id') or False,
                'partner_name': (
                    self.env['res.partner'].browse(int(filters['partner_id'])).display_name
                    if filters.get('partner_id') else False
                ),
            },
            'kpis': self._kc_compute_kpis(
                orders, previous_orders, currency, invoices, previous_invoices
            ),
            'sales_trend': sales_trend,
            'top_customers': top_customers,
            'sales_by_channel': sales_by_channel,
            'cash_vs_credit': cash_vs_credit,
            'orders_detail_title': self._kc_sales_period_label(
                date_from,
                date_to,
                _('Detalle de ventas del día'),
                _('Detalle de ventas del período'),
            ),
            'orders': {
                'total': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': max((total_count + page_size - 1) // page_size, 1),
                'lines': order_lines,
            },
        }

    @api.model
    def get_sales_dashboard_drilldown_action(self, drill_type, drill_value=None, filters=None):
        filters = filters or {}
        domain = self._kc_dashboard_base_domain(filters)
        name = _('Pedidos de venta')

        if drill_type == 'order':
            order = self.browse(int(drill_value))
            order.check_access('read')
            return {
                'type': 'ir.actions.act_window',
                'name': order.name,
                'res_model': 'sale.order',
                'res_id': order.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
            }

        if drill_type == 'hour' or drill_type.startswith('trend_'):
            granularity = 'hour' if drill_type == 'hour' else drill_type.replace('trend_', '', 1)
            trend_orders = self._kc_sales_trend_drilldown_orders(self.search(domain), granularity, drill_value)
            domain = [('id', 'in', trend_orders.ids)]
            if granularity == 'hour':
                name = _('Ventas de las %02d:00') % int(drill_value)
            elif granularity == 'day':
                day = fields.Date.from_string(drill_value)
                name = _('Ventas del %s') % day.strftime('%d/%m/%Y')
            elif granularity == 'week':
                week_start = fields.Date.from_string(drill_value)
                name = _('Ventas semana del %s') % week_start.strftime('%d/%m/%Y')
            else:
                year, month = map(int, drill_value.split('-'))
                name = _('Ventas de %s') % date(year, month, 1).strftime('%b %Y')

        elif drill_type == 'customer':
            domain = expression.AND([domain, [('partner_id', '=', int(drill_value))]])
            partner = self.env['res.partner'].browse(int(drill_value))
            name = partner.display_name

        elif drill_type == 'channel':
            team_id = int(drill_value)
            if team_id:
                domain = expression.AND([domain, [('team_id', '=', team_id)]])
                name = self.env['crm.team'].browse(team_id).name
            else:
                domain = expression.AND([domain, [('team_id', '=', False)]])
                name = _('Sin canal')

        elif drill_type == 'payment':
            payment_key = drill_value
            orders = self.search(domain)
            if payment_key == 'cash':
                order_ids = orders.filtered(lambda o: self._kc_order_payment_label(o) == 'cash').ids
                name = _('Ventas al contado')
            else:
                order_ids = orders.filtered(lambda o: self._kc_order_payment_label(o) == 'credit').ids
                name = _('Ventas a crédito')
            domain = [('id', 'in', order_ids)]

        elif drill_type == 'kpi_invoiced':
            domain = expression.AND([domain, [('invoice_status', '=', 'invoiced')]])
            name = _('Órdenes facturadas')

        elif drill_type == 'kpi_not_invoiced':
            domain = expression.AND([domain, [('invoice_status', '!=', 'invoiced')]])
            name = _('Órdenes no facturadas')

        elif drill_type == 'kpi_invoices':
            orders = self.search(domain)
            invoice_ids = self._kc_get_order_invoices(orders).ids
            return {
                'type': 'ir.actions.act_window',
                'name': _('Facturas'),
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', invoice_ids or [0])],
                'context': {'default_move_type': 'out_invoice'},
                'target': 'current',
            }

        elif drill_type in ('kpi_sales',):
            invoices = self._kc_get_dashboard_invoices(filters)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Ventas facturadas del período'),
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('id', 'in', invoices.ids or [0])],
                'context': {'default_move_type': 'out_invoice'},
                'target': 'current',
            }

        elif drill_type in ('kpi_customers', 'table'):
            pass

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
            'context': {'search_default_my_quotation': 0},
        }
