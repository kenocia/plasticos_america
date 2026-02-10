# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import io
import calendar
import datetime
from dateutil import parser

try:
    import xlwt
except ImportError:
    xlwt = None


class ReportExemptionsSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.exemptions_sar'
    _description = 'Reporte de Exenciones y Exoneraciones SAR'

    # Campos para configuración
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.today)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    
    # Campos para filtros
    exemption_type = fields.Selection([
        ('all', 'Todas las Exenciones'),
        ('exempt', 'Exento'),
        ('exonerated', 'Exonerado')
    ], string='Tipo de Exención', default='all', required=True)
    
    # Campos para resultados
    excel_file = fields.Binary(string='Archivo Excel', readonly=True)
    excel_filename = fields.Char(string='Nombre del Archivo', readonly=True)
    total_invoices = fields.Integer(string='Total Facturas', readonly=True)
    total_exempt = fields.Monetary(string='Monto Exento Total', readonly=True, currency_field='currency_id')
    total_exonerated = fields.Monetary(string='Monto Exonerado Total', readonly=True, currency_field='currency_id')
    
    def action_generate_report(self):
        """Generar reporte de exenciones y exoneraciones SAR"""
        self.ensure_one()
        
        # Validar fechas
        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser mayor a la fecha hasta'))
        
        # Obtener exenciones
        invoices = self.get_exemptions()
        
        if not invoices:
            raise ValidationError(_('No se encontraron facturas con exenciones en el rango de fechas especificado'))
        
        # Calcular totales
        self.total_invoices = len(invoices)
        self.total_exempt = sum(invoices.mapped('amount_exento'))
        self.total_exonerated = sum(invoices.mapped('amount_exonerado'))
        
        # Generar Excel
        return self.print_report()
    
    def print_report(self):
        """Generar reporte de exenciones SAR en Excel"""
        if not xlwt:
            raise ValidationError(_('La librería xlwt no está instalada'))
        
        invoices = self.get_exemptions()
        filename = f'Reporte_Exenciones_SAR_{self.date_from}_{self.date_to}.xls'
        
        workbook = xlwt.Workbook()
        style = xlwt.easyxf()
        encabezado = xlwt.easyxf('font: name Arial, color black, bold on, height 320; align: horiz center')
        titulos = xlwt.easyxf('font: name Arial, color black, bold on,; align: horiz center')
        subtitulos = xlwt.easyxf('font: name Arial, color black, bold on,height 250; align: horiz center')
        detalle = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda = xlwt.easyxf('font: name Arial, color black;')
        detalle_moneda.num_format_str = 'L#,##0.00'
        
        # Hoja 1: Resumen General
        sheet = workbook.add_sheet('Resumen General', cell_overwrite_ok=True)
        
        # Encabezado
        sheet.write_merge(0, 0, 0, 5, 'REPORTE DE EXENCIONES Y EXONERACIONES SAR - HONDURAS', encabezado)
        sheet.write_merge(1, 1, 0, 5, f'Período: {self.date_from} - {self.date_to}', subtitulos)
        
        # Información de la empresa
        sheet.write(3, 0, 'Empresa:', titulos)
        sheet.write(3, 1, self.company_id.name, detalle)
        sheet.write(4, 0, 'RTN:', titulos)
        sheet.write(4, 1, self.company_id.vat or 'N/A', detalle)
        
        # Totales generales
        sheet.write(6, 0, 'TOTALES GENERALES', encabezado)
        sheet.write(7, 0, 'Concepto', titulos)
        sheet.write(7, 1, 'Cantidad', titulos)
        sheet.write(7, 2, 'Monto', titulos)
        
        sheet.write(8, 0, 'Total Facturas', detalle)
        sheet.write(8, 1, len(invoices), detalle)
        sheet.write(8, 2, sum(invoices.mapped('amount_exento')), detalle_moneda)
        
        sheet.write(9, 0, 'Monto Exento Total', detalle)
        sheet.write(9, 2, sum(invoices.mapped('amount_exento')), detalle_moneda)
        
        sheet.write(10, 0, 'Monto Exonerado Total', detalle)
        sheet.write(10, 2, sum(invoices.mapped('amount_exonerado')), detalle_moneda)
        
        # Hoja 2: Detalle por Factura
        sheet_detail = workbook.add_sheet('Detalle por Factura', cell_overwrite_ok=True)
        
        # Encabezados
        headers = [
            'Número Factura', 'Fecha', 'Cliente/Proveedor', 'RTN', 'Tipo Documento',
            'Monto Exento', 'Monto Exonerado', 'Total Factura', 'CAI', 'Estado'
        ]
        
        for col, header in enumerate(headers):
            sheet_detail.write(0, col, header, titulos)
        
        # Datos
        row = 1
        for invoice in invoices:
            sheet_detail.write(row, 0, invoice.name or 'N/A', detalle)
            sheet_detail.write(row, 1, invoice.date.strftime('%d/%m/%Y') if invoice.date else 'N/A', detalle)
            sheet_detail.write(row, 2, invoice.partner_id.name or 'N/A', detalle)
            sheet_detail.write(row, 3, invoice.partner_id.vat or 'N/A', detalle)
            sheet_detail.write(row, 4, dict(invoice._fields['move_type'].selection)[invoice.move_type], detalle)
            sheet_detail.write(row, 5, invoice.amount_exento or 0, detalle_moneda)
            sheet_detail.write(row, 6, invoice.amount_exonerado or 0, detalle_moneda)
            sheet_detail.write(row, 7, invoice.amount_total or 0, detalle_moneda)
            sheet_detail.write(row, 8, invoice.cai or invoice.cai_proveedor or 'N/A', detalle)
            sheet_detail.write(row, 9, dict(invoice._fields['state'].selection)[invoice.state], detalle)
            row += 1
        
        # Hoja 3: Resumen por Tipo de Exención
        sheet_summary = workbook.add_sheet('Resumen por Tipo', cell_overwrite_ok=True)
        
        # Encabezados
        summary_headers = ['Tipo de Exención', 'Cantidad Facturas', 'Monto Total', 'Promedio por Factura']
        for col, header in enumerate(summary_headers):
            sheet_summary.write(0, col, header, titulos)
        
        # Agrupar por tipo de exención
        exemption_summary = {
            'Exento': {
                'count': len(invoices.filtered(lambda x: x.amount_exento > 0)),
                'amount': sum(invoices.mapped('amount_exento')),
                'avg': sum(invoices.mapped('amount_exento')) / len(invoices.filtered(lambda x: x.amount_exento > 0)) if invoices.filtered(lambda x: x.amount_exento > 0) else 0
            },
            'Exonerado': {
                'count': len(invoices.filtered(lambda x: x.amount_exonerado > 0)),
                'amount': sum(invoices.mapped('amount_exonerado')),
                'avg': sum(invoices.mapped('amount_exonerado')) / len(invoices.filtered(lambda x: x.amount_exonerado > 0)) if invoices.filtered(lambda x: x.amount_exonerado > 0) else 0
            }
        }
        
        # Escribir datos
        row = 1
        for exemption_type, data in exemption_summary.items():
            sheet_summary.write(row, 0, exemption_type, detalle)
            sheet_summary.write(row, 1, data['count'], detalle)
            sheet_summary.write(row, 2, data['amount'], detalle_moneda)
            sheet_summary.write(row, 3, data['avg'], detalle_moneda)
            row += 1
        
        # Hoja 4: Detalle de Productos Exentos/Exonerados
        sheet_products = workbook.add_sheet('Productos Exentos/Exonerados', cell_overwrite_ok=True)
        
        # Encabezados
        product_headers = [
            'Factura', 'Fecha', 'Producto', 'Cantidad', 'Precio Unitario',
            'Subtotal', 'Tipo Exención', 'Monto Exento/Exonerado'
        ]
        
        for col, header in enumerate(product_headers):
            sheet_products.write(0, col, header, titulos)
        
        # Datos de productos
        row = 1
        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                # Verificar si la línea tiene impuestos exentos o exonerados
                has_exempt_tax = any(tax.tax_group_id.name == 'Exento' for tax in line.tax_ids)
                has_exonerated_tax = any(tax.tax_group_id.name == 'Exonerado' for tax in line.tax_ids)
                
                if has_exempt_tax or has_exonerated_tax:
                    exemption_type = 'Exento' if has_exempt_tax else 'Exonerado'
                    exemption_amount = line.price_subtotal
                    
                    sheet_products.write(row, 0, invoice.name or 'N/A', detalle)
                    sheet_products.write(row, 1, invoice.date.strftime('%d/%m/%Y') if invoice.date else 'N/A', detalle)
                    sheet_products.write(row, 2, line.product_id.name or 'N/A', detalle)
                    sheet_products.write(row, 3, line.quantity, detalle)
                    sheet_products.write(row, 4, line.price_unit, detalle_moneda)
                    sheet_products.write(row, 5, line.price_subtotal, detalle_moneda)
                    sheet_products.write(row, 6, exemption_type, detalle)
                    sheet_products.write(row, 7, exemption_amount, detalle_moneda)
                    row += 1
        
        # Guardar archivo
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['kc_fiscal_hn.exemptions_sar.excel'].create(
            {'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        fp.close()
        
        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'kc_fiscal_hn.exemptions_sar.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
    
    def get_exemptions(self):
        """Obtener exenciones para el reporte"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['posted'])
        ]
        
        # Filtrar por tipo de exención
        if self.exemption_type == 'exempt':
            domain.append(('amount_exento', '>', 0))
        elif self.exemption_type == 'exonerated':
            domain.append(('amount_exonerado', '>', 0))
        else:
            domain.append('|')
            domain.append(('amount_exento', '>', 0))
            domain.append(('amount_exonerado', '>', 0))
        
        return self.env['account.move'].search(domain)
    
    def action_download_excel(self):
        """Descargar archivo Excel"""
        if not self.excel_file:
            raise ValidationError(_('Primero debe generar el reporte'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=excel_filename&download=true',
            'target': 'self',
        }


class ReportExemptionsSarExcel(models.TransientModel):
    _name = 'kc_fiscal_hn.exemptions_sar.excel'
    _description = 'Reporte de Exenciones SAR Excel'

    excel_file = fields.Binary('Archivo Excel', readonly=True)
    file_name = fields.Char('Nombre del Archivo', size=64)
    
    def action_download_excel(self):
        """Descargar archivo Excel"""
        if not self.excel_file:
            raise ValidationError(_('Primero debe generar el reporte'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=excel_filename&download=true',
            'target': 'self',
        } 