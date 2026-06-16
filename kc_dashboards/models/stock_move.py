# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.osv import expression


class StockMove(models.Model):
    _inherit = 'stock.move'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @api.model
    def _kc_uom_kg(self):
        return self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)

    @api.model
    def _kc_qty_to_kg(self, product, qty):
        uom_kg = self._kc_uom_kg()
        qty = qty or 0.0
        if not uom_kg or not product or not product.uom_id:
            return qty
        try:
            return product.uom_id._compute_quantity(qty, uom_kg)
        except Exception:
            return qty

    @api.model
    def _kc_move_qty_kg(self, move):
        qty = move.quantity if move.state == 'done' else move.product_uom_qty
        qty = move.product_uom._compute_quantity(qty or 0.0, move.product_id.uom_id)
        return self._kc_qty_to_kg(move.product_id, qty)

    @api.model
    def _kc_format_qty(self, qty):
        return f"{qty:,.2f}"

    @api.model
    def _kc_parse_date(self, date_value):
        if isinstance(date_value, str):
            return fields.Date.from_string(date_value)
        return date_value

    @api.model
    def _kc_day_bounds(self, date_value):
        date_value = self._kc_parse_date(date_value)
        return (
            fields.Datetime.to_string(datetime.combine(date_value, time.min)),
            fields.Datetime.to_string(datetime.combine(date_value, time.max)),
        )

    @api.model
    def _kc_date_range(self, filters):
        today = self._kc_default_movement_date()
        date_from = filters.get('date_from') or filters.get('date') or today
        date_to = filters.get('date_to') or filters.get('date') or date_from
        date_from = self._kc_parse_date(date_from)
        date_to = self._kc_parse_date(date_to)
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from, date_to

    @api.model
    def _kc_range_bounds(self, date_from, date_to):
        date_start, _ = self._kc_day_bounds(date_from)
        _, date_end = self._kc_day_bounds(date_to)
        return date_start, date_end

    @api.model
    def _kc_previous_range(self, date_from, date_to):
        days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        return prev_from, prev_to

    @api.model
    def _kc_period_label(self, date_from, date_to, single_label, period_label):
        days = (date_to - date_from).days + 1
        return single_label if days == 1 else period_label

    @api.model
    def _kc_default_movement_date(self):
        return fields.Date.context_today(self)

    @api.model
    def _kc_move_type(self, move):
        src = move.location_id.usage
        dest = move.location_dest_id.usage
        if src != 'internal' and dest == 'internal':
            return 'incoming', _('Entrada')
        if src == 'internal' and dest != 'internal':
            return 'outgoing', _('Salida')
        if src == 'internal' and dest == 'internal':
            return 'internal', _('Interno')
        return 'other', _('Otro')

    @api.model
    def _kc_movements_base_domain(self, filters):
        date_from, date_to = self._kc_date_range(filters)
        day_start, day_end = self._kc_range_bounds(date_from, date_to)
        domain = [
            ('state', '=', 'done'),
            ('date', '>=', day_start),
            ('date', '<=', day_end),
            ('product_id.is_storable', '=', True),
        ]
        if filters.get('warehouse_id'):
            warehouse = self.env['stock.warehouse'].browse(int(filters['warehouse_id']))
            if warehouse.exists():
                loc_id = warehouse.view_location_id.id
                domain = expression.AND([
                    domain,
                    ['|',
                     ('location_id', 'child_of', loc_id),
                     ('location_dest_id', 'child_of', loc_id)],
                ])
        if filters.get('location_id'):
            location = self.env['stock.location'].browse(int(filters['location_id']))
            if location.exists():
                domain = expression.AND([
                    domain,
                    ['|',
                     ('location_id', '=', location.id),
                     ('location_dest_id', '=', location.id)],
                ])
        if filters.get('product_id'):
            domain.append(('product_id', '=', int(filters['product_id'])))
        if filters.get('movement_type') and filters['movement_type'] != 'all':
            move_type = filters['movement_type']
            if move_type == 'incoming':
                domain = expression.AND([
                    domain,
                    [('location_id.usage', '!=', 'internal'),
                     ('location_dest_id.usage', '=', 'internal')],
                ])
            elif move_type == 'outgoing':
                domain = expression.AND([
                    domain,
                    [('location_id.usage', '=', 'internal'),
                     ('location_dest_id.usage', '!=', 'internal')],
                ])
            elif move_type == 'internal':
                domain = expression.AND([
                    domain,
                    [('location_id.usage', '=', 'internal'),
                     ('location_dest_id.usage', '=', 'internal')],
                ])
        return domain

    @api.model
    def _kc_movements_trend_data(self, moves, date_from, date_to):
        days = (date_to - date_from).days + 1
        if days == 1:
            granularity = 'hour'
            title = _('Movimientos por hora (kg)')
        elif days <= 31:
            granularity = 'day'
            title = _('Tendencia de movimientos por día (kg)')
        elif days <= 120:
            granularity = 'week'
            title = _('Tendencia de movimientos por semana (kg)')
        else:
            granularity = 'month'
            title = _('Tendencia de movimientos por mes (kg)')

        amounts_map = defaultdict(float)
        for move in moves:
            local_dt = fields.Datetime.context_timestamp(self, move.date)
            qty_kg = self._kc_move_qty_kg(move)
            if granularity == 'hour':
                bucket_key = str(local_dt.hour)
            elif granularity == 'day':
                bucket_key = fields.Date.to_string(local_dt.date())
            elif granularity == 'week':
                week_start = local_dt.date() - timedelta(days=local_dt.weekday())
                bucket_key = fields.Date.to_string(week_start)
            else:
                bucket_key = f'{local_dt.year}-{local_dt.month:02d}'
            amounts_map[bucket_key] += qty_kg

        points = []
        if granularity == 'hour':
            for hour in range(7, 19):
                bucket_key = str(hour)
                qty = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': f'{hour:02d}:00',
                    'qty': qty,
                    'qty_fmt': self._kc_format_qty(qty),
                })
        elif granularity == 'day':
            current = date_from
            while current <= date_to:
                bucket_key = fields.Date.to_string(current)
                qty = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%d/%m'),
                    'qty': qty,
                    'qty_fmt': self._kc_format_qty(qty),
                })
                current += timedelta(days=1)
        elif granularity == 'week':
            current = date_from - timedelta(days=date_from.weekday())
            while current <= date_to:
                bucket_key = fields.Date.to_string(current)
                qty = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%d/%m'),
                    'qty': qty,
                    'qty_fmt': self._kc_format_qty(qty),
                })
                current += timedelta(days=7)
        else:
            current = date_from.replace(day=1)
            while current <= date_to:
                bucket_key = f'{current.year}-{current.month:02d}'
                qty = amounts_map.get(bucket_key, 0.0)
                points.append({
                    'key': bucket_key,
                    'label': current.strftime('%b %Y'),
                    'qty': qty,
                    'qty_fmt': self._kc_format_qty(qty),
                })
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        max_qty = max((point['qty'] for point in points), default=0.0) or 1.0
        for point in points:
            point['pct'] = point['qty'] / max_qty * 100.0

        return {
            'granularity': granularity,
            'title': title,
            'points': points,
        }

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @api.model
    def get_movements_dashboard_filter_options(self):
        location_ids = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
        ]).mapped('location_id').ids
        locations = self.env['stock.location'].browse(location_ids).sorted(
            key=lambda loc: loc.complete_name
        )
        return {
            'locations': [{'id': loc.id, 'name': loc.display_name} for loc in locations[:500]],
            'movement_types': [
                {'id': 'all', 'name': _('Todos')},
                {'id': 'incoming', 'name': _('Entrada')},
                {'id': 'outgoing', 'name': _('Salida')},
                {'id': 'internal', 'name': _('Interno')},
            ],
        }

    @api.model
    def search_movements_dashboard_products(self, query='', limit=30):
        query = (query or '').strip()
        limit = min(max(int(limit or 30), 1), 50)
        product_ids = self.search([
            ('state', '=', 'done'),
            ('product_id.is_storable', '=', True),
        ], limit=5000).mapped('product_id').ids
        domain = [('id', 'in', product_ids or [0]), ('is_storable', '=', True)]
        if query:
            domain = expression.AND([
                domain,
                ['|', ('default_code', 'ilike', query), ('name', 'ilike', query)],
            ])
        products = self.env['product.product'].search(domain, limit=limit, order='display_name')
        return [{'id': product.id, 'name': product.display_name} for product in products]

    @api.model
    def _kc_count_moves_by_type(self, moves):
        incoming_kg = outgoing_kg = internal_kg = 0.0
        incoming_count = outgoing_count = internal_count = 0
        for move in moves:
            move_type, _label = self._kc_move_type(move)
            qty_kg = self._kc_move_qty_kg(move)
            if move_type == 'incoming':
                incoming_kg += qty_kg
                incoming_count += 1
            elif move_type == 'outgoing':
                outgoing_kg += qty_kg
                outgoing_count += 1
            elif move_type == 'internal':
                internal_kg += qty_kg
                internal_count += 1
        return {
            'incoming': (incoming_count, incoming_kg),
            'outgoing': (outgoing_count, outgoing_kg),
            'internal': (internal_count, internal_kg),
        }

    @api.model
    def get_movements_dashboard_data(self, filters=None, page=1, page_size=8):
        filters = filters or {}
        page = max(int(page or 1), 1)
        page_size = max(int(page_size or 8), 1)

        date_from, date_to = self._kc_date_range(filters)
        prev_from, prev_to = self._kc_previous_range(date_from, date_to)
        prev_filters = dict(filters)
        prev_filters.update({
            'date_from': fields.Date.to_string(prev_from),
            'date_to': fields.Date.to_string(prev_to),
        })
        prev_filters.pop('date', None)

        moves = self.search(self._kc_movements_base_domain(filters), order='date desc')
        prev_moves = self.search(self._kc_movements_base_domain(prev_filters))

        total_count = len(moves)
        total_kg = sum(self._kc_move_qty_kg(move) for move in moves)
        prev_count = len(prev_moves)
        prev_kg = sum(self._kc_move_qty_kg(move) for move in prev_moves)

        def _delta(current, previous):
            if not previous:
                return 100.0 if current else 0.0
            return ((current - previous) / previous) * 100.0

        type_totals = self._kc_count_moves_by_type(moves)
        prev_type_totals = self._kc_count_moves_by_type(prev_moves)
        incoming_count, incoming_kg = type_totals['incoming']
        outgoing_count, outgoing_kg = type_totals['outgoing']
        internal_count, internal_kg = type_totals['internal']
        prev_incoming_count, prev_incoming_kg = prev_type_totals['incoming']
        prev_outgoing_count, prev_outgoing_kg = prev_type_totals['outgoing']
        prev_internal_count, prev_internal_kg = prev_type_totals['internal']

        by_product = defaultdict(float)
        for move in moves:
            by_product[move.product_id.display_name] += self._kc_move_qty_kg(move)
        top_products = sorted(
            [
                {'name': name, 'qty': qty, 'qty_fmt': self._kc_format_qty(qty)}
                for name, qty in by_product.items()
            ],
            key=lambda item: item['qty'],
            reverse=True,
        )[:8]
        max_prod = top_products[0]['qty'] if top_products else 0.0
        for item in top_products:
            item['pct'] = (item['qty'] / max_prod * 100.0) if max_prod else 0.0

        by_type = [
            {'key': 'incoming', 'name': _('Entradas'), 'qty': incoming_kg, 'qty_fmt': self._kc_format_qty(incoming_kg), 'count': incoming_count},
            {'key': 'outgoing', 'name': _('Salidas'), 'qty': outgoing_kg, 'qty_fmt': self._kc_format_qty(outgoing_kg), 'count': outgoing_count},
            {'key': 'internal', 'name': _('Internos'), 'qty': internal_kg, 'qty_fmt': self._kc_format_qty(internal_kg), 'count': internal_count},
        ]
        total_type_kg = sum(item['qty'] for item in by_type) or 1.0
        for item in by_type:
            item['pct'] = item['qty'] / total_type_kg * 100.0

        movements_trend = self._kc_movements_trend_data(moves, date_from, date_to)

        offset = (page - 1) * page_size
        page_moves = moves[offset:offset + page_size]
        table_rows = []
        for move in page_moves:
            move_type, type_label = self._kc_move_type(move)
            qty_kg = self._kc_move_qty_kg(move)
            move_dt = fields.Datetime.context_timestamp(self, move.date)
            table_rows.append({
                'id': move.id,
                'datetime': move_dt.strftime('%d/%m/%Y %H:%M'),
                'reference': move.picking_id.name or move.reference or move.name or '-',
                'product': move.product_id.display_name,
                'origin': move.location_id.display_name,
                'dest': move.location_dest_id.display_name,
                'qty_kg_fmt': self._kc_format_qty(qty_kg),
                'type': type_label,
                'type_key': move_type,
                'status': dict(move._fields['state'].selection).get(move.state, move.state),
                'status_key': move.state,
            })

        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return {
            'title': _('Movimientos de inventario'),
            'company': {'id': self.env.company.id, 'name': self.env.company.name},
            'updated_at': now.strftime('%I:%M %p').replace('AM', 'a. m.').replace('PM', 'p. m.'),
            'filters': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'previous_date_from': fields.Date.to_string(prev_from),
                'previous_date_to': fields.Date.to_string(prev_to),
                'location_id': filters.get('location_id') or False,
                'product_id': filters.get('product_id') or False,
                'movement_type': filters.get('movement_type') or False,
            },
            'kpi_labels': {
                'total_movements': self._kc_period_label(
                    date_from, date_to,
                    _('Movimientos del día'),
                    _('Movimientos del período'),
                ),
            },
            'kpis': {
                'total_movements': {
                    'value': total_count,
                    'formatted': str(total_count),
                    'previous': prev_count,
                    'delta_pct': round(_delta(total_count, prev_count), 1),
                },
                'total_qty': {
                    'value': total_kg,
                    'formatted': self._kc_format_qty(total_kg),
                    'previous': self._kc_format_qty(prev_kg),
                    'delta_pct': round(_delta(total_kg, prev_kg), 1),
                },
                'incoming': {
                    'value': incoming_count,
                    'formatted': self._kc_format_qty(incoming_kg),
                    'previous': prev_incoming_count,
                    'delta_pct': round(_delta(incoming_count, prev_incoming_count), 1),
                },
                'outgoing': {
                    'value': outgoing_count,
                    'formatted': self._kc_format_qty(outgoing_kg),
                    'previous': prev_outgoing_count,
                    'delta_pct': round(_delta(outgoing_count, prev_outgoing_count), 1),
                },
                'internal': {
                    'value': internal_count,
                    'formatted': self._kc_format_qty(internal_kg),
                    'previous': prev_internal_count,
                    'delta_pct': round(_delta(internal_count, prev_internal_count), 1),
                },
            },
            'movements_by_type': by_type,
            'movements_trend': movements_trend,
            'top_products': top_products,
            'lines': {
                'total': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': max((total_count + page_size - 1) // page_size, 1),
                'rows': table_rows,
            },
        }

    @api.model
    def get_movements_dashboard_drilldown_action(self, drill_type, drill_value=None, filters=None):
        filters = filters or {}
        domain = self._kc_movements_base_domain(filters)
        name = _('Movimientos de inventario')

        if drill_type == 'move':
            move = self.browse(int(drill_value))
            if not move.exists():
                return False
            return {
                'type': 'ir.actions.act_window',
                'name': move.reference or move.name,
                'res_model': 'stock.move',
                'res_id': move.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
            }

        if drill_type == 'kpi_incoming':
            domain = expression.AND([
                domain,
                [('location_id.usage', '!=', 'internal'),
                 ('location_dest_id.usage', '=', 'internal')],
            ])
            name = _('Entradas')

        elif drill_type == 'kpi_outgoing':
            domain = expression.AND([
                domain,
                [('location_id.usage', '=', 'internal'),
                 ('location_dest_id.usage', '!=', 'internal')],
            ])
            name = _('Salidas')

        elif drill_type == 'kpi_internal':
            domain = expression.AND([
                domain,
                [('location_id.usage', '=', 'internal'),
                 ('location_dest_id.usage', '=', 'internal')],
            ])
            name = _('Movimientos internos')

        elif drill_type == 'movement_type':
            type_filters = dict(filters, movement_type=drill_value)
            domain = self._kc_movements_base_domain(type_filters)
            name = {
                'incoming': _('Entradas'),
                'outgoing': _('Salidas'),
                'internal': _('Internos'),
            }.get(drill_value, name)

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'stock.move',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }
