# -*- coding: utf-8 -*-
"""Wizard: reporte Excel de margen de ventas desde facturas publicadas."""

import base64
import io
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

# Meses en español para columna "Mes"
_MONTHS_ES = {
    1: 'Enero',
    2: 'Febrero',
    3: 'Marzo',
    4: 'Abril',
    5: 'Mayo',
    6: 'Junio',
    7: 'Julio',
    8: 'Agosto',
    9: 'Septiembre',
    10: 'Octubre',
    11: 'Noviembre',
    12: 'Diciembre',
}


class SalesMarginReportWizard(models.TransientModel):
    _name = 'kc.sales.margin.report.wizard'
    _description = 'Reporte margen de ventas (Excel)'

    date_from = fields.Date(
        string='Fecha desde',
        required=True,
        default=lambda self: fields.Date.start_of(fields.Date.context_today(self), 'month'),
    )
    date_to = fields.Date(
        string='Fecha hasta',
        required=True,
        default=lambda self: fields.Date.end_of(fields.Date.context_today(self), 'month'),
    )
    partner_ids = fields.Many2many('res.partner', string='Clientes')
    product_ids = fields.Many2many('product.product', string='Productos')
    category_ids = fields.Many2many('product.category', string='Categorías de producto')
    company_ids = fields.Many2many(
        'res.company',
        'kc_sales_margin_wizard_company_rel',
        'wizard_id',
        'company_id',
        string='Compañías',
        required=True,
        default=lambda self: self.env.companies,
    )
    move_state = fields.Selection(
        [('posted', 'Publicado')],
        string='Estado del documento',
        default='posted',
        required=True,
    )

    @api.constrains('company_ids')
    def _check_company_ids(self):
        for wiz in self:
            allowed = set(self.env.user.company_ids.ids)
            for cid in wiz.company_ids.ids:
                if cid not in allowed:
                    raise ValidationError(_('No tiene acceso a todas las compañías seleccionadas.'))

    def _report_currency_and_company(self):
        """Moneda de consolidación para KPIs: primera compañía seleccionada o la actual."""
        self.ensure_one()
        companies = self.company_ids
        if not companies:
            return self.env.company, self.env.company.currency_id
        report_company = companies[0]
        return report_company, report_company.currency_id

    def _to_report_currency(self, amount, from_currency, line_company, report_currency, date):
        """Convierte un importe a la moneda del reporte."""
        if not from_currency or not report_currency:
            return amount or 0.0
        if from_currency == report_currency:
            return amount or 0.0
        return from_currency._convert(amount, report_currency, line_company, date)

    def _line_sign(self, move):
        """Factura positiva, nota de crédito negativa (importes en valor absoluto de Odoo)."""
        return -1 if move.move_type == 'out_refund' else 1

    def _move_line_domain(self):
        self.ensure_one()
        domain = [
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('move_id.state', '=', self.move_state),
            ('move_id.invoice_date', '>=', self.date_from),
            ('move_id.invoice_date', '<=', self.date_to),
            ('move_id.company_id', 'in', self.company_ids.ids),
            ('display_type', '=', 'product'),
            ('product_id', '!=', False),
            ('product_id.is_storable', '=', True),
            ('product_id.type', 'not in', ('service', 'combo')),
        ]
        if self.partner_ids:
            domain.append(('move_id.partner_id', 'in', self.partner_ids.ids))
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        if self.category_ids:
            domain.append(('product_id.categ_id', 'child_of', self.category_ids.ids))
        return domain

    def _fetch_detail_rows(self):
        """Lista de dicts por línea válida, importes en moneda del reporte."""
        self.ensure_one()
        report_company, report_currency = self._report_currency_and_company()
        MoveLine = self.env['account.move.line']
        lines = MoveLine.search(self._move_line_domain(), order='move_id, id')
        lines = lines.sorted(
            key=lambda l: (l.move_id.invoice_date or l.move_id.date, l.move_id.id, l.id)
        )
        rows = []
        for line in lines:
            move = line.move_id
            product = line.product_id
            company = move.company_id
            sign = self._line_sign(move)
            inv_date = move.invoice_date or move.date
            line_currency = line.currency_id or move.currency_id

            raw_sub = line.price_subtotal or 0.0
            raw_total = line.price_total or 0.0
            sale_wo_tax = sign * abs(raw_sub)
            sale_w_tax = sign * abs(raw_total)
            qty = sign * abs(line.quantity or 0.0)

            product_comp = product.with_company(company)
            unit_cost = float(product_comp.standard_price or 0.0)
            company_currency = company.currency_id
            cost_total_company = qty * unit_cost

            sale_wo_tax_rc = self._to_report_currency(
                sale_wo_tax, line_currency, company, report_currency, inv_date
            )
            sale_w_tax_rc = self._to_report_currency(
                sale_w_tax, line_currency, company, report_currency, inv_date
            )
            cost_total_rc = self._to_report_currency(
                cost_total_company, company_currency, company, report_currency, inv_date
            )
            unit_cost_rc = (cost_total_rc / qty) if qty else 0.0

            gross_profit = sale_wo_tax_rc - cost_total_rc
            pct_margin = (gross_profit / sale_wo_tax_rc) if sale_wo_tax_rc else 0.0
            markup = (gross_profit / cost_total_rc) if cost_total_rc else 0.0

            doc_type = _('Nota de crédito') if move.move_type == 'out_refund' else _('Factura')
            month_label = ''
            if inv_date:
                month_label = '%s %s' % (_MONTHS_ES.get(inv_date.month, ''), inv_date.year)

            state_label = dict(move._fields['state']._description_selection(self.env)).get(
                move.state, move.state or ''
            )

            rows.append({
                'company': company.name,
                'invoice_date': inv_date,
                'month_label': month_label,
                'doc_type': doc_type,
                'move_name': move.name or '',
                'partner': move.partner_id.display_name or '',
                'salesperson': move.invoice_user_id.display_name or '',
                'product': product.display_name or '',
                'category': product.categ_id.display_name or '',
                'quantity': qty,
                'price_unit': line.price_unit or 0.0,
                'discount': line.discount or 0.0,
                'sale_wo_tax': sale_wo_tax_rc,
                'sale_w_tax': sale_w_tax_rc,
                'unit_cost': unit_cost_rc,
                'cost_total': cost_total_rc,
                'gross_profit': gross_profit,
                'pct_margin': pct_margin,
                'markup': markup,
                'state': state_label,
                'move_id': move.id,
                'partner_id': move.partner_id.id,
                'product_id': product.id,
                'salesperson_id': move.invoice_user_id.id if move.invoice_user_id else False,
                'categ_id': product.categ_id.id if product.categ_id else False,
                'move_type': move.move_type,
            })
        return rows, report_currency

    def _aggregate_groups(self, rows):
        """Agrupaciones para hojas resumen y bloques ejecutivos."""
        by_partner = defaultdict(lambda: {'sale_wo': 0.0, 'sale_w': 0.0, 'cost': 0.0})
        by_salesperson = defaultdict(lambda: {'sale_wo': 0.0, 'sale_w': 0.0, 'cost': 0.0})
        by_product = defaultdict(lambda: {'sale_wo': 0.0, 'sale_w': 0.0, 'cost': 0.0, 'categ': ''})
        by_categ = defaultdict(lambda: {'sale_wo': 0.0, 'sale_w': 0.0, 'cost': 0.0})
        by_month = defaultdict(lambda: {'sale_wo': 0.0, 'sale_w': 0.0, 'cost': 0.0})

        for r in rows:
            pid = r['partner_id']
            by_partner[pid]['name'] = r['partner']
            by_partner[pid]['sale_wo'] += r['sale_wo_tax']
            by_partner[pid]['sale_w'] += r['sale_w_tax']
            by_partner[pid]['cost'] += r['cost_total']

            key_sp = (r['salesperson_id'], r['salesperson'])
            sp_bucket = by_salesperson[key_sp]
            if 'name' not in sp_bucket:
                sp_bucket['name'] = r['salesperson'] or _('(Sin vendedor)')
            sp_bucket['sale_wo'] += r['sale_wo_tax']
            sp_bucket['sale_w'] += r['sale_w_tax']
            sp_bucket['cost'] += r['cost_total']

            prod_id = r['product_id']
            by_product[prod_id]['name'] = r['product']
            by_product[prod_id]['categ'] = r['category']
            by_product[prod_id]['sale_wo'] += r['sale_wo_tax']
            by_product[prod_id]['sale_w'] += r['sale_w_tax']
            by_product[prod_id]['cost'] += r['cost_total']

            cid = r['categ_id']
            by_categ[cid]['name'] = r['category'] or _('(Sin categoría)')
            by_categ[cid]['sale_wo'] += r['sale_wo_tax']
            by_categ[cid]['sale_w'] += r['sale_w_tax']
            by_categ[cid]['cost'] += r['cost_total']

            mkey = r['month_label'] or ''
            by_month[mkey]['sale_wo'] += r['sale_wo_tax']
            by_month[mkey]['sale_w'] += r['sale_w_tax']
            by_month[mkey]['cost'] += r['cost_total']

        def finalize(blocks):
            out = []
            for key, vals in blocks.items():
                sale_wo = vals['sale_wo']
                cost = vals['cost']
                prof = sale_wo - cost
                pm = (prof / sale_wo) if sale_wo else 0.0
                mu = (prof / cost) if cost else 0.0
                entry = {
                    'key': key,
                    'sale_wo': sale_wo,
                    'sale_w': vals['sale_w'],
                    'cost': cost,
                    'profit': prof,
                    'pct_margin': pm,
                    'markup': mu,
                }
                if 'name' in vals:
                    entry['name'] = vals['name']
                elif isinstance(key, tuple) and len(key) > 1:
                    entry['name'] = key[1] or _('(Sin vendedor)')
                if 'categ' in vals:
                    entry['categ'] = vals['categ']
                out.append(entry)
            return out

        partners = finalize(by_partner)
        partners.sort(key=lambda x: x['sale_wo'], reverse=True)

        salespeople = finalize(by_salesperson)
        salespeople.sort(key=lambda x: x['sale_wo'], reverse=True)

        products = []
        for pid, vals in by_product.items():
            sale_wo = vals['sale_wo']
            cost = vals['cost']
            prof = sale_wo - cost
            products.append({
                'key': pid,
                'name': vals['name'],
                'categ': vals['categ'],
                'sale_wo': sale_wo,
                'sale_w': vals['sale_w'],
                'cost': cost,
                'profit': prof,
                'pct_margin': (prof / sale_wo) if sale_wo else 0.0,
                'markup': (prof / cost) if cost else 0.0,
            })
        products.sort(key=lambda x: x['sale_wo'], reverse=True)

        categs = finalize(by_categ)
        categs.sort(key=lambda x: x['sale_wo'], reverse=True)

        months = finalize(by_month)
        months.sort(key=lambda x: x['key'])

        return {
            'partner': partners,
            'salesperson': salespeople,
            'product': products,
            'category': categs,
            'month': months,
        }

    def _currency_excel_format(self, currency):
        if not currency:
            return '#,##0.00'
        pos = currency.position
        sym = currency.symbol or ''
        if pos == 'before':
            return '%s#,##0.00' % sym.replace('"', '""')
        return '#,##0.00 %s' % sym.replace('"', '""')

    def _build_excel(self, rows, aggregates, report_currency):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            output,
            {'in_memory': True, 'remove_timezone': True},
        )
        cur_fmt_s = self._currency_excel_format(report_currency)
        money_fmt = workbook.add_format({'num_format': cur_fmt_s})
        qty_fmt = workbook.add_format({'num_format': '#,##0.00'})
        pct_fmt = workbook.add_format({'num_format': '0.00%'})
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'left',
        })
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': '#FFFFFF',
            'border': 1,
            'valign': 'vcenter',
        })
        subheader_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
        })
        label_fmt = workbook.add_format({'bold': True})
        cell_fmt = workbook.add_format({'valign': 'vcenter'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        dt_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy hh:mm'})

        move_ids = list({r['move_id'] for r in rows})
        moves = self.env['account.move'].browse(move_ids)
        refund_count = len(moves.filtered(lambda m: m.move_type == 'out_refund'))
        invoice_count = len(moves.filtered(lambda m: m.move_type == 'out_invoice'))
        partners_n = len({r['partner_id'] for r in rows})
        products_n = len({r['product_id'] for r in rows})

        total_wo = sum(r['sale_wo_tax'] for r in rows)
        total_w = sum(r['sale_w_tax'] for r in rows)
        total_cost = sum(r['cost_total'] for r in rows)
        total_profit = total_wo - total_cost
        glob_margin = (total_profit / total_wo) if total_wo else 0.0
        glob_markup = (total_profit / total_cost) if total_cost else 0.0
        n_moves = len(move_ids)
        ticket_avg = (total_wo / n_moves) if n_moves else 0.0
        sale_avg_inv = (total_w / n_moves) if n_moves else 0.0

        # --- Hoja 1: Resumen Ejecutivo ---
        ws0 = workbook.add_worksheet('Resumen Ejecutivo')
        ws0.set_column(0, 0, 42)
        ws0.set_column(1, 3, 22)
        r = 0
        ws0.merge_range(r, 0, r, 3, _('Margen de ventas (facturas publicadas)'), title_fmt)
        r += 2
        now_user = self.env.user
        gen_dt = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        ws0.write(r, 0, _('Periodo:'), label_fmt)
        ws0.write(r, 1, '%s — %s' % (self.date_from, self.date_to), cell_fmt)
        r += 1
        ws0.write(r, 0, _('Generado:'), label_fmt)
        ws0.write(r, 1, gen_dt, dt_fmt)
        r += 1
        ws0.write(r, 0, _('Usuario:'), label_fmt)
        ws0.write(r, 1, now_user.display_name, cell_fmt)
        r += 1
        ws0.write(r, 0, _('Moneda del reporte:'), label_fmt)
        ws0.write(r, 1, report_currency.display_name, cell_fmt)
        r += 1
        ws0.write(r, 0, _('Compañías:'), label_fmt)
        ws0.write(r, 1, ', '.join(self.company_ids.mapped('name')), cell_fmt)
        r += 1
        ws0.write(r, 0, _('Filtros:'), label_fmt)
        filt_parts = []
        if self.partner_ids:
            filt_parts.append(_('Clientes: %s') % ', '.join(self.partner_ids.mapped('display_name')[:20]))
            if len(self.partner_ids) > 20:
                filt_parts[-1] += '…'
        if self.product_ids:
            filt_parts.append(_('Productos seleccionados'))
        if self.category_ids:
            filt_parts.append(_('Categorías: %s') % ', '.join(self.category_ids.mapped('display_name')))
        ws0.write(r, 1, '; '.join(filt_parts) if filt_parts else _('Ninguno (todas las líneas válidas)'), cell_fmt)
        r += 2

        int_fmt = workbook.add_format({'num_format': '0'})
        kpis = [
            ('money', _('Venta total sin impuestos'), total_wo),
            ('money', _('Venta total con impuestos'), total_w),
            ('money', _('Costo total (estándar)'), total_cost),
            ('money', _('Utilidad bruta total'), total_profit),
            ('pct', _('Margen global (%)'), glob_margin),
            ('pct', _('Markup global'), glob_markup),
            ('int', _('Documentos analizados'), n_moves),
            ('int', _('Facturas'), invoice_count),
            ('int', _('Notas de crédito'), refund_count),
            ('int', _('Clientes (distintos)'), partners_n),
            ('int', _('Productos (distintos)'), products_n),
            ('money', _('Ticket promedio sin impuestos'), ticket_avg),
            ('money', _('Venta promedio con impuestos por documento'), sale_avg_inv),
        ]
        ws0.write(r, 0, _('Indicadores'), subheader_fmt)
        ws0.merge_range(r, 1, r, 3, '', subheader_fmt)
        r += 1
        for kind, lbl, val in kpis:
            ws0.write(r, 0, lbl, label_fmt)
            if kind == 'money':
                ws0.write_number(r, 1, val, money_fmt)
            elif kind == 'pct':
                ws0.write_number(r, 1, val, pct_fmt)
            else:
                ws0.write_number(r, 1, val, int_fmt)
            r += 1

        def write_block(title, data_rows, name_col_title, extra_cols=None):
            nonlocal r
            r += 1
            ws0.merge_range(r, 0, r, 6, title, subheader_fmt)
            r += 1
            headers = [name_col_title, _('Venta s/imp.'), _('Venta c/imp.'), _('Costo'), _('Utilidad'), _('% margen'), _('Markup')]
            for c, h in enumerate(headers):
                ws0.write(r, c, h, header_fmt)
            r += 1
            for row in data_rows:
                ws0.write(r, 0, row.get('name', row.get('key', '')), cell_fmt)
                ws0.write_number(r, 1, row['sale_wo'], money_fmt)
                ws0.write_number(r, 2, row['sale_w'], money_fmt)
                ws0.write_number(r, 3, row['cost'], money_fmt)
                ws0.write_number(r, 4, row['profit'], money_fmt)
                ws0.write_number(r, 5, row['pct_margin'], pct_fmt)
                ws0.write_number(r, 6, row['markup'], pct_fmt)
                r += 1

        write_block(_('Por cliente'), aggregates['partner'], _('Cliente'))
        sp_rows = aggregates['salesperson']
        write_block(_('Por vendedor'), sp_rows, _('Vendedor'))
        prod_rows = list(aggregates['product'])
        write_block(_('Por producto'), prod_rows, _('Producto'))
        write_block(_('Por categoría'), aggregates['category'], _('Categoría'))
        write_block(_('Por mes'), aggregates['month'], _('Mes'))

        # --- Detalle por línea ---
        ws1 = workbook.add_worksheet('Detalle por Línea')
        det_headers = [
            _('Compañía'), _('Fecha factura'), _('Mes'), _('Tipo documento'), _('Número'),
            _('Cliente'), _('Vendedor'), _('Producto'), _('Categoría'), _('Cantidad'),
            _('Precio unitario'), _('Descuento %'), _('Venta s/imp.'), _('Venta c/imp.'),
            _('Costo unitario'), _('Costo total'), _('Utilidad bruta'), _('% margen'),
            _('Markup'), _('Estado'),
        ]
        for c, h in enumerate(det_headers):
            ws1.write(0, c, h, header_fmt)
        ws1.freeze_panes(1, 0)
        ws1.autofilter(0, 0, max(len(rows), 1), len(det_headers) - 1)
        row_i = 1
        for rec in rows:
            ws1.write(row_i, 0, rec['company'], cell_fmt)
            ws1.write(row_i, 1, rec['invoice_date'], date_fmt)
            ws1.write(row_i, 2, rec['month_label'], cell_fmt)
            ws1.write(row_i, 3, rec['doc_type'], cell_fmt)
            ws1.write(row_i, 4, rec['move_name'], cell_fmt)
            ws1.write(row_i, 5, rec['partner'], cell_fmt)
            ws1.write(row_i, 6, rec['salesperson'], cell_fmt)
            ws1.write(row_i, 7, rec['product'], cell_fmt)
            ws1.write(row_i, 8, rec['category'], cell_fmt)
            ws1.write_number(row_i, 9, rec['quantity'], qty_fmt)
            ws1.write_number(row_i, 10, rec['price_unit'], money_fmt)
            ws1.write_number(row_i, 11, rec['discount'] / 100.0 if rec['discount'] else 0.0, pct_fmt)
            ws1.write_number(row_i, 12, rec['sale_wo_tax'], money_fmt)
            ws1.write_number(row_i, 13, rec['sale_w_tax'], money_fmt)
            ws1.write_number(row_i, 14, rec['unit_cost'], money_fmt)
            ws1.write_number(row_i, 15, rec['cost_total'], money_fmt)
            ws1.write_number(row_i, 16, rec['gross_profit'], money_fmt)
            ws1.write_number(row_i, 17, rec['pct_margin'], pct_fmt)
            ws1.write_number(row_i, 18, rec['markup'], pct_fmt)
            ws1.write(row_i, 19, rec['state'], cell_fmt)
            row_i += 1

        if rows:
            ws1.write(row_i, 0, _('TOTAL'), header_fmt)
            ws1.write_number(row_i, 9, sum(r['quantity'] for r in rows), qty_fmt)
            ws1.write_number(row_i, 12, total_wo, money_fmt)
            ws1.write_number(row_i, 13, total_w, money_fmt)
            ws1.write_number(row_i, 15, total_cost, money_fmt)
            ws1.write_number(row_i, 16, total_profit, money_fmt)
            ws1.write_number(row_i, 17, glob_margin, pct_fmt)
            ws1.write_number(row_i, 18, glob_markup, pct_fmt)

        widths = [20, 12, 14, 14, 18, 28, 18, 35, 22, 12, 14, 10, 16, 16, 14, 14, 14, 10, 10, 12]
        for i, w in enumerate(widths):
            ws1.set_column(i, i, w)

        def summary_sheet(name, rows_src, col_title, with_categ=False):
            ws = workbook.add_worksheet(name)
            headers = [col_title]
            if with_categ:
                headers.append(_('Categoría'))
            headers.extend([
                _('Venta s/imp.'), _('Venta c/imp.'), _('Costo total'),
                _('Utilidad bruta'), _('% margen'), _('Markup'),
            ])
            for c, h in enumerate(headers):
                ws.write(0, c, h, header_fmt)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(rows_src), 1), len(headers) - 1)
            ri = 1
            for item in rows_src:
                c0 = item.get('name', item.get('key', ''))
                if isinstance(c0, tuple):
                    c0 = c0[1] or _('(Sin vendedor)')
                ws.write(ri, 0, c0, cell_fmt)
                off = 1
                if with_categ:
                    ws.write(ri, 1, item.get('categ', ''), cell_fmt)
                    off = 2
                ws.write_number(ri, off, item['sale_wo'], money_fmt)
                ws.write_number(ri, off + 1, item['sale_w'], money_fmt)
                ws.write_number(ri, off + 2, item['cost'], money_fmt)
                ws.write_number(ri, off + 3, item['profit'], money_fmt)
                ws.write_number(ri, off + 4, item['pct_margin'], pct_fmt)
                ws.write_number(ri, off + 5, item['markup'], pct_fmt)
                ri += 1
            for i in range(len(headers)):
                ws.set_column(i, i, 22)

        summary_sheet(_('Resumen por Cliente')[:31], aggregates['partner'], _('Cliente'))
        summary_sheet(_('Resumen por Vendedor')[:31], sp_rows, _('Vendedor'))
        # Producto con categoría
        ws_p = workbook.add_worksheet('Resumen por Producto')
        h_prod = [_('Producto'), _('Categoría'), _('Venta s/imp.'), _('Venta c/imp.'), _('Costo total'), _('Utilidad bruta'), _('% margen'), _('Markup')]
        for c, h in enumerate(h_prod):
            ws_p.write(0, c, h, header_fmt)
        ws_p.freeze_panes(1, 0)
        ws_p.autofilter(0, 0, max(len(aggregates['product']), 1), len(h_prod) - 1)
        ri = 1
        for item in aggregates['product']:
            ws_p.write(ri, 0, item['name'], cell_fmt)
            ws_p.write(ri, 1, item['categ'], cell_fmt)
            ws_p.write_number(ri, 2, item['sale_wo'], money_fmt)
            ws_p.write_number(ri, 3, item['sale_w'], money_fmt)
            ws_p.write_number(ri, 4, item['cost'], money_fmt)
            ws_p.write_number(ri, 5, item['profit'], money_fmt)
            ws_p.write_number(ri, 6, item['pct_margin'], pct_fmt)
            ws_p.write_number(ri, 7, item['markup'], pct_fmt)
            ri += 1
        for i in range(len(h_prod)):
            ws_p.set_column(i, i, 28)

        summary_sheet(_('Resumen por Categoría')[:31], aggregates['category'], _('Categoría'))
        summary_sheet(_('Resumen por Mes')[:31], aggregates['month'], _('Mes'))

        workbook.close()
        output.seek(0)
        return output.getvalue()

    def action_generate_excel(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser posterior a la fecha hasta.'))
        if not xlsxwriter:
            raise UserError(_('Instale la librería Python "xlsxwriter" en el servidor.'))
        if not self.company_ids:
            raise UserError(_('Seleccione al menos una compañía.'))

        rows, report_currency = self._fetch_detail_rows()
        if not rows:
            raise UserError(_('No hay líneas que cumplan los criterios (facturas publicadas, productos almacenables).'))

        aggregates = self._aggregate_groups(rows)
        content = self._build_excel(rows, aggregates, report_currency)

        df = self.date_from.strftime('%Y%m%d')
        dt = self.date_to.strftime('%Y%m%d')
        filename = 'Margen_Ventas_%s_%s.xlsx' % (df, dt)

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(content).decode('ascii'),
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
