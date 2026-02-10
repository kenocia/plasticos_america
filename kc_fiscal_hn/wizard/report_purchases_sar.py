# -*- coding: utf-8 -*-

import base64
import io
from odoo import fields, models, _
from odoo.exceptions import ValidationError

try:
    import xlwt
except ImportError:
    xlwt = None


class ReportPurchasesSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.purchases_sar'
    _description = 'Reporte de Compras SAR'

    # Campos para configuración
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.today)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)

    # Campos para filtros
    include_draft = fields.Boolean(string='Incluir Borradores', default=False)
    include_cancelled = fields.Boolean(string='Incluir Canceladas', default=False)
    group_by_tax_rate = fields.Boolean(string='Agrupar por Tasa de Impuesto', default=True)
    group_by_vendor_type = fields.Boolean(string='Agrupar por Tipo de Proveedor', default=True)

    # Campos para resultados
    excel_file = fields.Binary(string='Archivo Excel', readonly=True)
    excel_filename = fields.Char(string='Nombre del Archivo', readonly=True)
    total_invoices = fields.Integer(string='Total Documentos', readonly=True)
    total_amount = fields.Monetary(string='Monto Total', readonly=True, currency_field='currency_id')
    total_isv = fields.Monetary(string='ISV Total', readonly=True, currency_field='currency_id')
    total_exempt = fields.Monetary(string='Exento Total', readonly=True, currency_field='currency_id')
    total_exonerated = fields.Monetary(string='Exonerado Total', readonly=True, currency_field='currency_id')

    def _signed_value(self, invoice, value):
        """Aplicar signo negativo a notas de crédito de compra."""
        sign = -1 if invoice.move_type == 'in_refund' else 1
        return sign * abs(value or 0.0)

    def get_invoices(self):
        """Obtener facturas de proveedor para el reporte."""
        domain = [
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]

        if not self.include_draft:
            domain.append(('state', '!=', 'draft'))

        if not self.include_cancelled:
            domain.append(('state', '!=', 'cancel'))

        return self.env['account.move'].search(domain)

    def action_generate_report(self):
        """Generar reporte de compras SAR."""
        self.ensure_one()

        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser mayor a la fecha hasta'))

        invoices = self.get_invoices()

        if not invoices:
            raise ValidationError(_('No se encontraron facturas en el rango de fechas especificado'))

        self.total_invoices = len(invoices)
        self.total_amount = sum(self._signed_value(inv, inv.amount_total) for inv in invoices)
        self.total_isv = sum(self._signed_value(inv, inv.isv_total) for inv in invoices)
        self.total_exempt = sum(self._signed_value(inv, inv.amount_exento) for inv in invoices)
        self.total_exonerated = sum(self._signed_value(inv, inv.amount_exonerado) for inv in invoices)

        return self.print_report()

    def print_report(self):
        """Generar reporte de compras SAR en Excel."""
        if not xlwt:
            raise ValidationError(_('La librería xlwt no está instalada'))

        invoices = self.get_invoices()
        filename = f'Reporte_Compras_SAR_{self.date_from}_{self.date_to}.xls'

        workbook = xlwt.Workbook()
        encabezado = xlwt.easyxf('font: name Arial, color black, bold on, height 320; align: horiz center')
        titulos = xlwt.easyxf('font: name Arial, color black, bold on,; align: horiz center')
        subtitulos = xlwt.easyxf('font: name Arial, color black, bold on,height 250; align: horiz center')
        detalle = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda.num_format_str = 'L#,##0.00'

        # Hoja 1: Resumen General
        sheet = workbook.add_sheet('Resumen General', cell_overwrite_ok=True)

        sheet.write_merge(0, 0, 0, 5, 'REPORTE DE COMPRAS SAR - HONDURAS', encabezado)
        sheet.write_merge(1, 1, 0, 5, f'Período: {self.date_from} - {self.date_to}', subtitulos)

        sheet.write(3, 0, 'Empresa:', titulos)
        sheet.write(3, 1, self.company_id.name, detalle)
        sheet.write(4, 0, 'RTN:', titulos)
        sheet.write(4, 1, self.company_id.vat or 'N/A', detalle)

        sheet.write(6, 0, 'TOTALES GENERALES', encabezado)
        sheet.write(7, 0, 'Concepto', titulos)
        sheet.write(7, 1, 'Cantidad', titulos)
        sheet.write(7, 2, 'Monto', titulos)

        sheet.write(8, 0, 'Total Documentos', detalle)
        sheet.write(8, 1, len(invoices), detalle)
        sheet.write(8, 2, sum(self._signed_value(inv, inv.amount_total) for inv in invoices), detalle_moneda)

        sheet.write(9, 0, 'ISV Total', detalle)
        sheet.write(9, 2, sum(self._signed_value(inv, inv.isv_total) for inv in invoices), detalle_moneda)

        sheet.write(10, 0, 'Exento Total', detalle)
        sheet.write(10, 2, sum(self._signed_value(inv, inv.amount_exento) for inv in invoices), detalle_moneda)

        sheet.write(11, 0, 'Exonerado Total', detalle)
        sheet.write(11, 2, sum(self._signed_value(inv, inv.amount_exonerado) for inv in invoices), detalle_moneda)

        # Hoja 2: Detalle por Documento
        sheet_detail = workbook.add_sheet('Detalle por Documento', cell_overwrite_ok=True)

        headers = [
            'Número Documento', 'Fecha', 'Proveedor', 'RTN Proveedor', 'Base Imponible',
            'ISV 15%', 'Base 15%', 'ISV 18%', 'Base 18%', 'Exento', 'Exonerado',
            'Descuento', 'Total', 'CAI', 'Estado'
        ]

        for col, header in enumerate(headers):
            sheet_detail.write(0, col, header, titulos)

        row = 1
        for invoice in invoices:
            sheet_detail.write(row, 0, invoice.name or 'N/A', detalle)
            sheet_detail.write(row, 1, invoice.date.strftime('%d/%m/%Y') if invoice.date else 'N/A', detalle)
            sheet_detail.write(row, 2, invoice.partner_id.name or 'N/A', detalle)
            sheet_detail.write(row, 3, invoice.partner_id.vat or 'N/A', detalle)
            sheet_detail.write(row, 4, self._signed_value(invoice, invoice.base_imponible_total), detalle_moneda)
            sheet_detail.write(row, 5, self._signed_value(invoice, invoice.amount_isv15), detalle_moneda)
            sheet_detail.write(row, 6, self._signed_value(invoice, invoice.gravado_isv15), detalle_moneda)
            sheet_detail.write(row, 7, self._signed_value(invoice, invoice.amount_isv18), detalle_moneda)
            sheet_detail.write(row, 8, self._signed_value(invoice, invoice.gravado_isv18), detalle_moneda)
            sheet_detail.write(row, 9, self._signed_value(invoice, invoice.amount_exento), detalle_moneda)
            sheet_detail.write(row, 10, self._signed_value(invoice, invoice.amount_exonerado), detalle_moneda)
            sheet_detail.write(row, 11, self._signed_value(invoice, invoice.amount_discount), detalle_moneda)
            sheet_detail.write(row, 12, self._signed_value(invoice, invoice.amount_total), detalle_moneda)
            sheet_detail.write(row, 13, invoice.cai or 'N/A', detalle)
            sheet_detail.write(row, 14, dict(invoice._fields['state'].selection)[invoice.state], detalle)
            row += 1

        # Hoja 3: Resumen por Tasa de Impuesto
        if self.group_by_tax_rate:
            sheet_tax = workbook.add_sheet('Resumen por Tasa', cell_overwrite_ok=True)

            tax_headers = ['Tasa de Impuesto', 'Cantidad Documentos', 'Base Imponible', 'ISV', 'Total']
            for col, header in enumerate(tax_headers):
                sheet_tax.write(0, col, header, titulos)

            tax_summary = {}
            for invoice in invoices:
                if abs(invoice.amount_isv15 or 0) > 0:
                    if '15%' not in tax_summary:
                        tax_summary['15%'] = {'count': 0, 'base': 0, 'tax': 0, 'total': 0}
                    base_15 = self._signed_value(invoice, invoice.gravado_isv15)
                    tax_15 = self._signed_value(invoice, invoice.amount_isv15)
                    tax_summary['15%']['count'] += 1
                    tax_summary['15%']['base'] += base_15
                    tax_summary['15%']['tax'] += tax_15
                    tax_summary['15%']['total'] += base_15 + tax_15

                if abs(invoice.amount_isv18 or 0) > 0:
                    if '18%' not in tax_summary:
                        tax_summary['18%'] = {'count': 0, 'base': 0, 'tax': 0, 'total': 0}
                    base_18 = self._signed_value(invoice, invoice.gravado_isv18)
                    tax_18 = self._signed_value(invoice, invoice.amount_isv18)
                    tax_summary['18%']['count'] += 1
                    tax_summary['18%']['base'] += base_18
                    tax_summary['18%']['tax'] += tax_18
                    tax_summary['18%']['total'] += base_18 + tax_18

            row = 1
            for tax_rate, data in tax_summary.items():
                sheet_tax.write(row, 0, tax_rate, detalle)
                sheet_tax.write(row, 1, data['count'], detalle)
                sheet_tax.write(row, 2, data['base'], detalle_moneda)
                sheet_tax.write(row, 3, data['tax'], detalle_moneda)
                sheet_tax.write(row, 4, data['total'], detalle_moneda)
                row += 1

        # Hoja 4: Resumen por Tipo de Proveedor
        if self.group_by_vendor_type:
            sheet_vendor = workbook.add_sheet('Resumen por Proveedor', cell_overwrite_ok=True)

            vendor_headers = ['Tipo Proveedor', 'Cantidad Documentos', 'Base Imponible', 'ISV', 'Total']
            for col, header in enumerate(vendor_headers):
                sheet_vendor.write(0, col, header, titulos)

            vendor_summary = {
                'Con RTN': {'count': 0, 'base': 0, 'tax': 0, 'total': 0},
                'Sin RTN': {'count': 0, 'base': 0, 'tax': 0, 'total': 0},
            }

            for invoice in invoices:
                vendor_type = 'Con RTN' if invoice.partner_id.vat else 'Sin RTN'
                vendor_summary[vendor_type]['count'] += 1
                vendor_summary[vendor_type]['base'] += self._signed_value(invoice, invoice.base_imponible_total)
                vendor_summary[vendor_type]['tax'] += self._signed_value(invoice, invoice.isv_total)
                vendor_summary[vendor_type]['total'] += self._signed_value(invoice, invoice.amount_total)

            row = 1
            for vendor_type, data in vendor_summary.items():
                sheet_vendor.write(row, 0, vendor_type, detalle)
                sheet_vendor.write(row, 1, data['count'], detalle)
                sheet_vendor.write(row, 2, data['base'], detalle_moneda)
                sheet_vendor.write(row, 3, data['tax'], detalle_moneda)
                sheet_vendor.write(row, 4, data['total'], detalle_moneda)
                row += 1

        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['kc_fiscal_hn.purchases_sar.excel'].create(
            {'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename}
        )
        fp.close()

        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'kc_fiscal_hn.purchases_sar.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class ReportPurchasesSarExcel(models.TransientModel):
    _name = 'kc_fiscal_hn.purchases_sar.excel'
    _description = 'Reporte de Compras SAR Excel'

    excel_file = fields.Binary('Archivo Excel', readonly=True)
    file_name = fields.Char('Nombre del Archivo', size=64)
