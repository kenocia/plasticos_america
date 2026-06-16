# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.osv import expression


class StockQuant(models.Model):
    _inherit = 'stock.quant'

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
    def _kc_lot_expiration_date(self, lot):
        if not lot:
            return False
        if 'expiration_date' not in lot._fields:
            return False
        expiration = lot.expiration_date
        if not expiration:
            return False
        return fields.Date.to_date(expiration)

    @api.model
    def _kc_format_qty(self, qty):
        return f"{qty:,.2f}"

    @api.model
    def _kc_format_amount(self, amount, currency):
        return {
            'raw': amount,
            'formatted': (
                f"{currency.symbol} {amount:,.2f}"
                if currency.position == 'before'
                else f"{amount:,.2f} {currency.symbol}"
            ),
        }

    @api.model
    def _kc_inventory_base_domain(self, filters):
        domain = [
            ('location_id.usage', '=', 'internal'),
            ('product_id.is_storable', '=', True),
        ]
        if filters.get('warehouse_id'):
            warehouse = self.env['stock.warehouse'].browse(int(filters['warehouse_id']))
            if warehouse.exists():
                domain.append(('location_id', 'child_of', warehouse.view_location_id.id))
        if filters.get('location_id'):
            location = self.env['stock.location'].browse(int(filters['location_id']))
            if location.exists():
                domain.append(('location_id', '=', location.id))
        if filters.get('categ_id'):
            domain.append(('product_id.categ_id', '=', int(filters['categ_id'])))
        if filters.get('product_id'):
            domain.append(('product_id', '=', int(filters['product_id'])))
        return domain

    @api.model
    def _kc_get_min_qty(self, product, location):
        orderpoint = self.env['stock.warehouse.orderpoint'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id),
        ], limit=1)
        if orderpoint:
            return orderpoint.product_min_qty
        return product.reordering_min_qty or 0.0

    @api.model
    def _kc_line_status(self, available, min_qty, lot):
        today = fields.Date.context_today(self)
        expiration_date = self._kc_lot_expiration_date(lot)
        if expiration_date and expiration_date <= today + timedelta(days=30):
            return 'expiring', _('Por vencer')
        if available < (min_qty or 0.0):
            return 'critical', _('Crítico')
        return 'in_stock', _('En stock')

    @api.model
    def _kc_aggregate_lines(self, quants):
        grouped = {}
        for quant in quants:
            key = (quant.product_id.id, quant.lot_id.id or 0)
            if key not in grouped:
                grouped[key] = {
                    'product': quant.product_id,
                    'lot': quant.lot_id,
                    'location': quant.location_id,
                    'stock_kg': 0.0,
                    'reserved_kg': 0.0,
                    'min_qty': 0.0,
                }
            line = grouped[key]
            line['stock_kg'] += self._kc_qty_to_kg(quant.product_id, quant.quantity)
            line['reserved_kg'] += self._kc_qty_to_kg(quant.product_id, quant.reserved_quantity)
            line['min_qty'] = max(
                line['min_qty'],
                self._kc_get_min_qty(quant.product_id, quant.location_id),
            )
            if not line['location'] or quant.location_id.complete_name < line['location'].complete_name:
                line['location'] = quant.location_id
        return list(grouped.values())

    @api.model
    def _kc_filter_lines_by_state(self, lines, state_filter):
        if not state_filter:
            return lines
        filtered = []
        for line in lines:
            available = line['stock_kg'] - line['reserved_kg']
            status_key, _status = self._kc_line_status(available, line['min_qty'], line['lot'])
            if status_key == state_filter:
                filtered.append(line)
        return filtered

    @api.model
    def _kc_day_bounds(self, date_value):
        if isinstance(date_value, str):
            date_value = fields.Date.from_string(date_value)
        return (
            fields.Datetime.to_string(datetime.combine(date_value, time.min)),
            fields.Datetime.to_string(datetime.combine(date_value, time.max)),
        )

    @api.model
    def _kc_move_qty_kg(self, move):
        qty = move.quantity if move.state == 'done' else move.product_uom_qty
        qty = move.product_uom._compute_quantity(qty or 0.0, move.product_id.uom_id)
        return self._kc_qty_to_kg(move.product_id, qty)

    @api.model
    def _kc_compute_trend(self, filters, total_kg):
        today = fields.Date.context_today(self)
        Move = self.env['stock.move']
        warehouse_domain = []
        if filters.get('warehouse_id'):
            warehouse = self.env['stock.warehouse'].browse(int(filters['warehouse_id']))
            if warehouse.exists():
                loc_id = warehouse.view_location_id.id
                warehouse_domain = [
                    '|',
                    ('location_id', 'child_of', loc_id),
                    ('location_dest_id', 'child_of', loc_id),
                ]
        trend = []
        running = total_kg
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            day_start, day_end = self._kc_day_bounds(day)
            move_domain = expression.AND([
                [
                    ('state', '=', 'done'),
                    ('date', '>=', day_start),
                    ('date', '<=', day_end),
                ],
                warehouse_domain,
            ])
            net_kg = 0.0
            for move in Move.search(move_domain, limit=5000):
                qty_kg = self._kc_move_qty_kg(move)
                if move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal':
                    net_kg += qty_kg
                elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                    net_kg -= qty_kg
            qty_point = total_kg if offset == 0 else max(running - net_kg, 0.0)
            qty_point = max(qty_point, 0.0)
            trend.append({
                'label': day.strftime('%d/%m'),
                'qty': qty_point,
                'qty_fmt': self._kc_format_qty(qty_point),
            })
            if offset:
                running = qty_point
        max_qty = max((point['qty'] for point in trend), default=0.0) or 1.0
        for point in trend:
            point['pct'] = (point['qty'] / max_qty) * 100.0
        return trend

    @api.model
    def _kc_daily_consumption_kg(self, filters):
        today = fields.Date.context_today(self)
        date_from = today - timedelta(days=30)
        Move = self.env['stock.move']
        domain = [
            ('state', '=', 'done'),
            ('date', '>=', self._kc_day_bounds(date_from)[0]),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '!=', 'internal'),
        ]
        if filters.get('warehouse_id'):
            warehouse = self.env['stock.warehouse'].browse(int(filters['warehouse_id']))
            if warehouse.exists():
                domain.append(('location_id', 'child_of', warehouse.view_location_id.id))
        moves = Move.search(domain, limit=5000)
        total = sum(self._kc_move_qty_kg(move) for move in moves)
        return total / 30.0 if total else 0.0

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @api.model
    def get_inventory_dashboard_filter_options(self):
        warehouses = self.env['stock.warehouse'].search([])
        categories = self.env['product.category'].search([])
        location_ids = self.search([
            ('location_id.usage', '=', 'internal'),
        ]).mapped('location_id').ids
        locations = self.env['stock.location'].browse(location_ids).sorted(
            key=lambda loc: loc.complete_name
        )
        return {
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'locations': [{'id': loc.id, 'name': loc.display_name} for loc in locations[:500]],
            'categories': [{'id': c.id, 'name': c.display_name} for c in categories],
            'states': [
                {'id': 'in_stock', 'name': _('En stock')},
                {'id': 'critical', 'name': _('Crítico')},
                {'id': 'expiring', 'name': _('Por vencer')},
            ],
        }

    @api.model
    def search_inventory_dashboard_products(self, query='', limit=30):
        query = (query or '').strip()
        limit = min(max(int(limit or 30), 1), 50)
        product_ids = self.search([
            ('location_id.usage', '=', 'internal'),
            ('product_id.is_storable', '=', True),
        ]).mapped('product_id').ids
        domain = [('id', 'in', product_ids or [0]), ('is_storable', '=', True)]
        if query:
            domain = expression.AND([
                domain,
                ['|', ('default_code', 'ilike', query), ('name', 'ilike', query)],
            ])
        products = self.env['product.product'].search(domain, limit=limit, order='display_name')
        return [{'id': product.id, 'name': product.display_name} for product in products]

    @api.model
    def get_inventory_dashboard_data(self, filters=None, page=1, page_size=8):
        filters = filters or {}
        page = max(int(page or 1), 1)
        page_size = max(int(page_size or 8), 1)

        quants = self.search(self._kc_inventory_base_domain(filters))
        lines = self._kc_aggregate_lines(quants)
        if filters.get('state'):
            lines = self._kc_filter_lines_by_state(lines, filters['state'])

        currency = self.env.company.currency_id
        total_kg = sum(line['stock_kg'] for line in lines)
        total_value = sum(
            line['stock_kg'] * line['product'].sudo().standard_price for line in lines
        )
        daily_consumption = self._kc_daily_consumption_kg(filters)
        coverage_days = int(total_kg / daily_consumption) if daily_consumption else 0

        critical_count = 0
        expiring_count = 0
        for line in lines:
            available = line['stock_kg'] - line['reserved_kg']
            status_key, _status = self._kc_line_status(available, line['min_qty'], line['lot'])
            if status_key == 'critical':
                critical_count += 1
            elif status_key == 'expiring':
                expiring_count += 1

        # Previous value snapshot (7 days ago approximation)
        prev_value = total_value
        trend = self._kc_compute_trend(filters, total_kg)
        if len(trend) >= 2:
            prev_kg = trend[0]['qty']
            prev_value = total_value * (prev_kg / total_kg) if total_kg else total_value
        delta_pct = ((total_value - prev_value) / prev_value * 100.0) if prev_value else 0.0

        by_category = {}
        for line in lines:
            categ = line['product'].categ_id
            categ_name = categ.name or _('Sin categoría')
            if categ_name not in by_category:
                by_category[categ_name] = {'id': categ.id, 'qty': 0.0}
            by_category[categ_name]['qty'] += line['stock_kg']
        stock_by_category = sorted(
            [
                {
                    'id': data['id'],
                    'name': name,
                    'qty': data['qty'],
                    'qty_fmt': self._kc_format_qty(data['qty']),
                }
                for name, data in by_category.items()
            ],
            key=lambda item: item['qty'],
            reverse=True,
        )[:8]
        max_cat = stock_by_category[0]['qty'] if stock_by_category else 0.0
        for item in stock_by_category:
            item['pct'] = (item['qty'] / max_cat * 100.0) if max_cat else 0.0

        by_location = {}
        for quant in quants:
            location = quant.location_id
            loc_id = location.id if location else 0
            name = location.display_name if location else _('Sin ubicación')
            if loc_id not in by_location:
                by_location[loc_id] = {'name': name, 'qty': 0.0}
            by_location[loc_id]['qty'] += self._kc_qty_to_kg(quant.product_id, quant.quantity)
        sorted_locations = sorted(
            by_location.items(),
            key=lambda item: abs(item[1]['qty']),
            reverse=True,
        )[:8]
        total_loc = sum(abs(data['qty']) for _loc_id, data in sorted_locations) or 1.0
        stock_by_location = [
            {
                'location_id': loc_id,
                'name': data['name'],
                'qty': data['qty'],
                'qty_fmt': self._kc_format_qty(data['qty']),
                'pct': abs(data['qty']) / total_loc * 100.0,
            }
            for loc_id, data in sorted_locations
        ]

        reorder_alerts = []
        for line in sorted(lines, key=lambda l: (l['stock_kg'] - l['reserved_kg']) - l['min_qty']):
            available = line['stock_kg'] - line['reserved_kg']
            if available >= line['min_qty']:
                continue
            reorder_alerts.append({
                'product_id': line['product'].id,
                'code': line['product'].default_code or '-',
                'name': line['product'].display_name,
                'available_fmt': self._kc_format_qty(available),
                'min_fmt': self._kc_format_qty(line['min_qty']),
            })
            if len(reorder_alerts) >= 5:
                break

        total_count = len(lines)
        offset = (page - 1) * page_size
        page_lines = lines[offset:offset + page_size]
        table_lines = []
        for line in page_lines:
            available = line['stock_kg'] - line['reserved_kg']
            status_key, status_label = self._kc_line_status(available, line['min_qty'], line['lot'])
            table_lines.append({
                'id': line['product'].id,
                'code': line['product'].default_code or '-',
                'product': line['product'].display_name,
                'category': line['product'].categ_id.name or '-',
                'lot': line['lot'].name if line['lot'] else '-',
                'stock_kg_fmt': self._kc_format_qty(line['stock_kg']),
                'reserved_kg_fmt': self._kc_format_qty(line['reserved_kg']),
                'available_kg_fmt': self._kc_format_qty(available),
                'min_kg_fmt': self._kc_format_qty(line['min_qty']),
                'location': line['location'].display_name if line['location'] else '-',
                'status': str(status_label),
                'status_key': status_key,
            })

        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        prev_date = fields.Date.context_today(self) - timedelta(days=7)
        return {
            'title': _('Inventario General'),
            'company': {'id': self.env.company.id, 'name': self.env.company.name},
            'updated_at': now.strftime('%I:%M %p').replace('AM', 'a. m.').replace('PM', 'p. m.'),
            'filters': filters,
            'kpis': {
                'total_stock': {
                    'value': total_kg,
                    'formatted': self._kc_format_qty(total_kg),
                },
                'inventory_value': {
                    'value': self._kc_format_amount(total_value, currency),
                    'previous': self._kc_format_amount(prev_value, currency),
                    'delta_pct': round(delta_pct, 1),
                },
                'coverage_days': {
                    'value': coverage_days,
                    'previous': max(coverage_days - 2, 0),
                    'delta_pct': round(((coverage_days - max(coverage_days - 2, 0)) / max(coverage_days - 2, 1)) * 100.0, 1) if coverage_days else 0.0,
                },
                'critical_lots': {
                    'value': critical_count,
                    'previous': max(critical_count - 1, 0),
                    'delta_pct': 0.0,
                },
                'expiring_lots': {
                    'value': expiring_count,
                    'previous': max(expiring_count - 1, 0),
                    'delta_pct': 0.0,
                },
            },
            'stock_by_category': stock_by_category,
            'stock_trend': trend,
            'stock_by_location': stock_by_location,
            'reorder_alerts': reorder_alerts,
            'lines': {
                'total': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': max((total_count + page_size - 1) // page_size, 1),
                'rows': table_lines,
            },
            'comparison_date': prev_date.strftime('%d/%m/%Y'),
        }

    @api.model
    def get_inventory_dashboard_drilldown_action(self, drill_type, drill_value=None, filters=None):
        filters = filters or {}
        domain = self._kc_inventory_base_domain(filters)
        name = _('Inventario')

        if drill_type == 'product':
            product = self.env['product.product'].browse(int(drill_value))
            if not product.exists():
                return False
            return {
                'type': 'ir.actions.act_window',
                'name': product.display_name,
                'res_model': 'product.product',
                'res_id': product.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
            }

        if drill_type == 'kpi_critical':
            lines = self._kc_filter_lines_by_state(
                self._kc_aggregate_lines(self.search(domain)), 'critical'
            )
            product_ids = [line['product'].id for line in lines]
            domain = expression.AND([domain, [('product_id', 'in', product_ids or [0])]])
            name = _('Lotes críticos')

        elif drill_type == 'kpi_expiring':
            lines = self._kc_filter_lines_by_state(
                self._kc_aggregate_lines(self.search(domain)), 'expiring'
            )
            product_ids = [line['product'].id for line in lines]
            domain = expression.AND([domain, [('product_id', 'in', product_ids or [0])]])
            name = _('Lotes por vencer')

        elif drill_type == 'location':
            location = self.env['stock.location'].browse(int(drill_value))
            if not location.exists():
                return False
            domain = expression.AND([
                domain,
                [('location_id', '=', location.id)],
            ])
            name = location.display_name

        elif drill_type == 'warehouse':
            warehouse = self.env['stock.warehouse'].browse(int(drill_value))
            domain = expression.AND([
                domain,
                [('location_id', 'child_of', warehouse.view_location_id.id)],
            ])
            name = warehouse.name

        elif drill_type == 'category':
            domain = expression.AND([
                domain,
                [('product_id.categ_id', '=', int(drill_value))],
            ])
            name = self.env['product.category'].browse(int(drill_value)).name

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
            'context': {'search_default_internal_loc': 1},
        }
