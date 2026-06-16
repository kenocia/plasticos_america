# -*- coding: utf-8 -*-
"""Generación del libro Excel (xlsxwriter): Facturas, Detalle Ventas, Resumen Fiscal."""

import base64
import io

from odoo import _

from .net_sales_report_invoice_list import format_move_type_label, state_label

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


def _require_xlsxwriter():
    if not xlsxwriter:
        from odoo.exceptions import ValidationError

        raise ValidationError(
            _("La librería xlsxwriter no está instalada. Instálela con: pip install xlsxwriter")
        )


def build_net_sales_xlsx(env, detail_rows, invoice_sheet_rows, fiscal_monthly_rows, company_currency):
    """
    invoice_sheet_rows: salida de build_invoice_sheet_rows (section, line, subtotal, grand).
    detail_rows: agregación por producto/cliente/categoría.
    fiscal_monthly_rows: filas mes a mes + total (aggregate_fiscal_monthly_rows).
    """
    _require_xlsxwriter()
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    header_fmt = workbook.add_format({
        "bold": True,
        "align": "center",
        "valign": "vcenter",
        "text_wrap": True,
    })
    cell_fmt = workbook.add_format({"valign": "vcenter"})
    number_fmt = workbook.add_format({"num_format": "#,##0.00"})
    money_fmt = workbook.add_format({"num_format": "#,##0.00"})
    date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})
    section_fmt = workbook.add_format({"bold": True, "bg_color": "#333F4F", "font_color": "#FFFFFF"})
    subtotal_fmt = workbook.add_format({"bold": True, "num_format": "#,##0.00", "bg_color": "#E8E8E8"})
    grand_fmt = workbook.add_format({"bold": True, "num_format": "#,##0.00", "bg_color": "#D7E4BD"})

    cur = company_currency
    cur_name = cur.name if cur else ""

    # --- Hoja 1: Facturas (vista lista / agrupada por mes, como en Odoo) ---
    sheet_inv = workbook.add_worksheet("Facturas")
    sheet_inv.set_column("A:A", 14)
    sheet_inv.set_column("B:B", 18)
    sheet_inv.set_column("C:C", 36)
    sheet_inv.set_column("D:E", 14)
    sheet_inv.set_column("F:G", 18)
    sheet_inv.set_column("H:H", 14)
    sheet_inv.freeze_panes(1, 0)

    inv_headers = [
        _("Tipo"),
        _("Número"),
        _("Cliente"),
        _("Fecha factura"),
        _("Fecha vencimiento"),
        _("Impuestos no incluidos") + ((" (%s)" % cur_name) if cur_name else ""),
        _("Total") + ((" (%s)" % cur_name) if cur_name else ""),
        _("Estado"),
    ]
    for col, h in enumerate(inv_headers):
        sheet_inv.write(0, col, h, header_fmt)

    row = 1
    for item in invoice_sheet_rows:
        kind = item["kind"]
        if kind == "section":
            sheet_inv.merge_range(row, 0, row, 7, item["title"], section_fmt)
            row += 1
        elif kind == "line":
            m = item["move"]
            sheet_inv.write(row, 0, format_move_type_label(m), cell_fmt)
            sheet_inv.write(row, 1, m.name or "", cell_fmt)
            sheet_inv.write(row, 2, m.partner_id.display_name or "", cell_fmt)
            sheet_inv.write(row, 3, m.invoice_date or "", date_fmt)
            sheet_inv.write(row, 4, m.invoice_date_due or "", date_fmt)
            sheet_inv.write(row, 5, item["untaxed"], money_fmt)
            sheet_inv.write(row, 6, item["total"], money_fmt)
            sheet_inv.write(row, 7, state_label(m, env), cell_fmt)
            row += 1
        elif kind == "subtotal":
            sheet_inv.merge_range(row, 0, row, 4, _("Subtotal del mes"), subtotal_fmt)
            sheet_inv.write(row, 5, item["untaxed"], subtotal_fmt)
            sheet_inv.write(row, 6, item["total"], subtotal_fmt)
            row += 1
        elif kind == "grand":
            sheet_inv.merge_range(row, 0, row, 4, _("Total"), grand_fmt)
            sheet_inv.write(row, 5, item["untaxed"], grand_fmt)
            sheet_inv.write(row, 6, item["total"], grand_fmt)
            row += 1

    # --- Hoja 2: Detalle por producto (pivote: producto, cant., P.U., total) ---
    sheet_d = workbook.add_worksheet("Detalle Ventas")
    sheet_d.set_column("A:A", 52)
    sheet_d.set_column("B:B", 36)
    sheet_d.set_column("C:C", 28)
    sheet_d.set_column("D:F", 18)
    sheet_d.freeze_panes(1, 0)

    headers_detail = [
        _("Producto"),
        _("Cliente"),
        _("Categoría"),
        _("Cant. facturada"),
        _("Precio unitario"),
        _("Total sin Impuesto"),
    ]
    for col, h in enumerate(headers_detail):
        sheet_d.write(0, col, h, header_fmt)

    row = 1
    if not detail_rows:
        sheet_d.merge_range(
            row, 0, row, 5,
            _(
                "No hay líneas de producto en el periodo (solo asientos sin detalle de producto o filtros muy restrictivos)."
            ),
            cell_fmt,
        )
    else:
        for r in detail_rows:
            sheet_d.write(row, 0, r["product_label"], cell_fmt)
            sheet_d.write(row, 1, r["partner_name"], cell_fmt)
            sheet_d.write(row, 2, r["categ_name"], cell_fmt)
            sheet_d.write(row, 3, r["qty"], number_fmt)
            sheet_d.write(row, 4, r["avg_price"], number_fmt)
            sheet_d.write(row, 5, r["untaxed"], money_fmt)
            row += 1

    # --- Hoja 3: Resumen fiscal (por mes + total; ventana de fechas propia del wizard) ---
    sheet_f = workbook.add_worksheet("Resumen Fiscal")
    sheet_f.set_column("A:A", 28)
    sheet_f.set_column("B:D", 22)
    sheet_f.freeze_panes(1, 0)

    headers_f = [
        _("Mes"),
        _("Subtotal"),
        _("ISV"),
        _("Total"),
    ]
    if cur_name:
        headers_f = [
            _("Mes"),
            _("Subtotal") + " (%s)" % cur_name,
            _("ISV") + " (%s)" % cur_name,
            _("Total") + " (%s)" % cur_name,
        ]
    for col, h in enumerate(headers_f):
        sheet_f.write(0, col, h, header_fmt)

    f_row = 1
    for fr in fiscal_monthly_rows:
        if fr["kind"] == "month":
            sheet_f.write(f_row, 0, fr["title"], cell_fmt)
            sheet_f.write(f_row, 1, fr["subtotal"], money_fmt)
            sheet_f.write(f_row, 2, fr["tax"], money_fmt)
            sheet_f.write(f_row, 3, fr["total"], money_fmt)
        else:
            sheet_f.write(f_row, 0, fr["title"], grand_fmt)
            sheet_f.write(f_row, 1, fr["subtotal"], grand_fmt)
            sheet_f.write(f_row, 2, fr["tax"], grand_fmt)
            sheet_f.write(f_row, 3, fr["total"], grand_fmt)
        f_row += 1

    workbook.close()
    output.seek(0)
    return output.getvalue()


def action_export_attachment(env, wizard, filename_base, content):
    """Crea adjunto y devuelve acción de descarga."""
    attachment = env["ir.attachment"].create({
        "name": filename_base,
        "datas": base64.b64encode(content).decode("ascii"),
        "res_model": wizard._name,
        "res_id": wizard.id,
        "type": "binary",
    })
    return {
        "type": "ir.actions.act_url",
        "url": "/web/content/%s?download=true" % attachment.id,
        "target": "self",
    }
