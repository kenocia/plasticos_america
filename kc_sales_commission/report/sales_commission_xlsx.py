# -*- coding: utf-8 -*-
import base64
import io
import re

from odoo import _, fields
from odoo.exceptions import UserError


def _sanitize_filename_part(text):
    if not text:
        return 'empleado'
    return re.sub(r'[^\w\-.]+', '_', text.strip())[:80]


def _currency_excel_num_format(currency):
    """Odoo estándar puede no tener campo excel_format en res.currency."""
    return getattr(currency, 'excel_format', None) or '#,##0.00'


def _commission_mode_label(commission):
    data = commission.fields_get(['commission_calc_mode'])
    sel = data.get('commission_calc_mode', {}).get('selection') or []
    for value, label in sel:
        if value == commission.commission_calc_mode:
            return label
    return commission.commission_calc_mode or ''


def generate_commission_excel_action(commission):
    """Genera el XLSX y devuelve la acción de descarga (ir.actions.act_url)."""
    try:
        import xlsxwriter
    except ImportError as err:
        raise UserError(
            _('Falta la librería Python "xlsxwriter". Instálela en el servidor Odoo.')
        ) from err

    commission.ensure_one()
    env = commission.env
    movetype_label = {'out_invoice': 'Factura', 'out_refund': 'Nota crédito'}
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
    currency = commission.currency_id
    currency_fmt = workbook.add_format({'num_format': _currency_excel_num_format(currency)})

    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#E8E0D8', 'border': 1})
    title_fmt = workbook.add_format({'bold': True, 'font_size': 12})
    cover_title = workbook.add_format({
        'bold': True,
        'font_size': 18,
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#F5EFE8',
        'border': 1,
    })
    cover_subtitle = workbook.add_format({'bold': True, 'font_size': 13, 'align': 'center'})
    cover_label = workbook.add_format({'bold': True, 'bg_color': '#FFF9F5'})
    cover_box = workbook.add_format({'border': 1})
    section_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'bg_color': '#D4C4B8', 'border': 1})

    # --- Portada ---
    ws0 = workbook.add_worksheet('Portada')
    ws0.set_column(0, 0, 22)
    ws0.set_column(1, 5, 40)
    ws0.merge_range(0, 0, 0, 5, _('Comisión de ventas'), cover_title)
    ws0.set_row(0, 32)
    company_name = commission.company_id.name or ''
    ws0.merge_range(2, 0, 2, 5, company_name, cover_subtitle)
    ws0.set_row(2, 22)

    r = 4
    emission = fields.Date.context_today(commission)
    emission_str = emission.strftime('%d/%m/%Y') if emission else ''

    info_rows = [
        (_('Referencia'), commission.name or ''),
        (_('Empleado'), commission.employee_id.display_name or ''),
        (_('Periodo'), '%s — %s' % (
            commission.date_from.strftime('%d/%m/%Y') if commission.date_from else '',
            commission.date_to.strftime('%d/%m/%Y') if commission.date_to else '',
        )),
        (_('Base de cálculo'), _commission_mode_label(commission)),
        (_('Fecha de exportación'), emission_str),
    ]
    for label, value in info_rows:
        ws0.write(r, 0, label, cover_label)
        ws0.merge_range(r, 1, r, 5, value, cover_box)
        r += 1

    r += 1
    ws0.merge_range(r, 0, r, 5, _('Resumen'), section_fmt)
    r += 1
    money_fmt = workbook.add_format({'border': 1, 'num_format': _currency_excel_num_format(currency)})
    summary = [
        (_('Total clientes'), commission.total_clients, False),
        (_('Total facturas'), commission.total_invoices, False),
        (_('Total venta'), commission.total_amount, True),
        (_('Total comisión'), commission.total_commission, True),
    ]
    for label, val, is_money in summary:
        ws0.write(r, 0, label, cover_label)
        cell_fmt = money_fmt if is_money else cover_box
        ws0.merge_range(r, 1, r, 5, val, cell_fmt)
        r += 1

    # --- Clientes y facturas (unificado) ---
    ws_cf = workbook.add_worksheet('Clientes y facturas')
    ws_cf.set_column(0, 0, 36)
    ws_cf.set_column(1, 7, 14)

    row = 0
    ws_cf.merge_range(row, 0, row, 6, _('Clientes asignados'), title_fmt)
    row += 1
    ws_cf.write(row, 0, _('Nº'), header_fmt)
    ws_cf.write(row, 1, _('Cliente'), header_fmt)
    row += 1
    n = 1
    for line in commission.client_line_ids:
        ws_cf.write(row, 0, n)
        ws_cf.write(row, 1, line.partner_id.display_name or '')
        n += 1
        row += 1

    row += 2
    ws_cf.merge_range(row, 0, row, 6, _('Facturas del periodo'), title_fmt)
    row += 1
    headers_inv = [
        _('Cliente'),
        _('Tipo'),
        _('Fecha'),
        _('Factura'),
        _('Subtotal'),
        _('ISV'),
        _('Total'),
    ]
    for col, h in enumerate(headers_inv):
        ws_cf.write(row, col, h, header_fmt)
    row += 1
    ws_cf.freeze_panes(row, 0)
    for line in commission.invoice_line_ids:
        ws_cf.write(row, 0, line.partner_id.display_name or '')
        ws_cf.write(row, 1, movetype_label.get(line.move_type, '') or '')
        ws_cf.write(
            row,
            2,
            line.invoice_date.strftime('%Y-%m-%d') if line.invoice_date else '',
        )
        ws_cf.write(row, 3, line.invoice_name or '')
        ws_cf.write_number(row, 4, line.amount_untaxed or 0.0, currency_fmt)
        ws_cf.write_number(row, 5, line.amount_tax or 0.0, currency_fmt)
        ws_cf.write_number(row, 6, line.amount_total or 0.0, currency_fmt)
        row += 1
    if commission.invoice_line_ids:
        ws_cf.write(row, 3, _('Totales'), header_fmt)
        ws_cf.write_number(row, 4, commission.total_subtotal, currency_fmt)
        ws_cf.write_number(row, 5, commission.total_tax, currency_fmt)
        ws_cf.write_number(row, 6, commission.total_amount, currency_fmt)

    # --- Detalle por producto ---
    ws3 = workbook.add_worksheet('Detalle producto')
    ws3.freeze_panes(2, 0)
    ws3.write(0, 0, _('Detalle por producto'), title_fmt)
    headers3 = [
        _('Tipo'),
        _('Fecha'),
        _('Cliente'),
        _('Código producto'),
        _('Producto'),
        _('Unidades'),
        _('Precio unitario'),
        _('Venta'),
        _('Comisión aplicada'),
        _('Total comisión'),
    ]
    for col, h in enumerate(headers3):
        ws3.write(1, col, h, header_fmt)
    row = 2
    for line in commission.detail_line_ids:
        ws3.write(row, 0, movetype_label.get(line.move_type, '') or '')
        ws3.write(
            row,
            1,
            line.invoice_date.strftime('%Y-%m-%d') if line.invoice_date else '',
        )
        ws3.write(row, 2, line.partner_id.display_name or '')
        ws3.write(row, 3, line.product_code or '')
        ws3.write(row, 4, line.product_id.display_name or '')
        ws3.write_number(row, 5, line.quantity or 0.0)
        ws3.write_number(row, 6, line.price_unit or 0.0)
        ws3.write_number(row, 7, line.sale_amount or 0.0, currency_fmt)
        ws3.write_number(row, 8, line.commission_rate or 0.0)
        ws3.write_number(row, 9, line.commission_amount or 0.0, currency_fmt)
        row += 1
    if commission.detail_line_ids:
        ws3.write(row, 8, _('Total'), header_fmt)
        ws3.write_number(row, 9, commission.total_commission, currency_fmt)
    ws3.set_column(0, 1, 12)
    ws3.set_column(2, 4, 26)
    ws3.set_column(5, 9, 14)

    workbook.close()
    data = buffer.getvalue()
    buffer.close()

    emp_part = _sanitize_filename_part(commission.employee_id.name)
    df = commission.date_from.strftime('%Y%m%d') if commission.date_from else ''
    dt = commission.date_to.strftime('%Y%m%d') if commission.date_to else ''
    filename = f'Comision_{emp_part}_{df}_{dt}.xlsx'

    attachment = env['ir.attachment'].create({
        'name': filename,
        'type': 'binary',
        'datas': base64.b64encode(data),
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }
