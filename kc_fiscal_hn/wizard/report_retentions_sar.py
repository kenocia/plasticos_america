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


class ReportRetentionsSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.retentions_sar'
    _description = 'Reporte de Retenciones SAR'

    # Campos para configuración
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.today)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    
    # Campos para filtros
    retention_type = fields.Selection([
        ('all', 'Todas las Retenciones'),
        ('isr', 'ISR'),
        ('isv', 'ISV'),
        ('other', 'Otras Retenciones')
    ], string='Tipo de Retención', default='all', required=True)
    
    # Campos para resultados
    excel_file = fields.Binary(string='Archivo Excel', readonly=True)
    excel_filename = fields.Char(string='Nombre del Archivo', readonly=True)
    total_retentions = fields.Integer(string='Total Retenciones', readonly=True)
    total_amount = fields.Monetary(string='Monto Total Retenido', readonly=True, currency_field='currency_id')
    total_base = fields.Monetary(string='Base Imponible Total', readonly=True, currency_field='currency_id')
    
    def action_generate_report(self):
        """Generar reporte de retenciones SAR"""
        self.ensure_one()
        
        # Validar fechas
        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser mayor a la fecha hasta'))
        
        # Obtener retenciones
        invoices = self.get_retentions()
        
        if not invoices:
            raise ValidationError(_('No se encontraron retenciones en el rango de fechas especificado'))
        
        # Calcular totales
        self.total_retentions = len(invoices)
        self.total_amount = sum(invoices.mapped('amount_total'))
        
        # Calcular base imponible total
        total_base = 0
        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                if line.tax_ids:
                    total_base += line.price_subtotal
        self.total_base = total_base
        
        # Generar Excel
        return self.print_report()
    
    def print_report(self):
        """Generar reporte de retenciones SAR en Excel"""
        if not xlwt:
            raise ValidationError(_('La librería xlwt no está instalada'))
        
        invoices = self.get_retentions()
        filename = f'Reporte_Retenciones_SAR_{self.date_from}_{self.date_to}.xls'
        
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
        sheet.write_merge(0, 0, 0, 5, 'REPORTE DE RETENCIONES SAR - HONDURAS', encabezado)
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
        
        sheet.write(8, 0, 'Total Retenciones', detalle)
        sheet.write(8, 1, len(invoices), detalle)
        sheet.write(8, 2, sum(invoices.mapped('amount_total')), detalle_moneda)
        
        # Calcular base imponible total
        total_base = 0
        for invoice in invoices:
            for line in invoice.invoice_line_ids:
                if line.tax_ids:
                    total_base += line.price_subtotal
        
        sheet.write(9, 0, 'Base Imponible Total', detalle)
        sheet.write(9, 2, total_base, detalle_moneda)
        
        # Hoja 2: Detalle por Retención
        sheet_detail = workbook.add_sheet('Detalle por Retención', cell_overwrite_ok=True)
        
        # Encabezados
        headers = [
            'Número Factura', 'Fecha', 'Proveedor', 'RTN Proveedor', 'Base Imponible',
            'Tipo Retención', 'Porcentaje', 'Monto Retenido', 'Total Factura',
            'CAI Proveedor', 'Estado'
        ]
        
        for col, header in enumerate(headers):
            sheet_detail.write(0, col, header, titulos)
        
        # Datos
        row = 1
        for invoice in invoices:
            # Obtener información de retenciones
            retention_info = self._get_retention_info(invoice)
            
            sheet_detail.write(row, 0, invoice.name or 'N/A', detalle)
            sheet_detail.write(row, 1, invoice.date.strftime('%d/%m/%Y') if invoice.date else 'N/A', detalle)
            sheet_detail.write(row, 2, invoice.partner_id.name or 'N/A', detalle)
            sheet_detail.write(row, 3, invoice.partner_id.vat or 'N/A', detalle)
            sheet_detail.write(row, 4, retention_info['base'], detalle_moneda)
            sheet_detail.write(row, 5, retention_info['type'], detalle)
            sheet_detail.write(row, 6, f"{retention_info['rate']}%", detalle)
            sheet_detail.write(row, 7, retention_info['amount'], detalle_moneda)
            sheet_detail.write(row, 8, invoice.amount_total or 0, detalle_moneda)
            sheet_detail.write(row, 9, invoice.cai_proveedor or 'N/A', detalle)
            sheet_detail.write(row, 10, dict(invoice._fields['state'].selection)[invoice.state], detalle)
            row += 1
        
        # Hoja 3: Resumen por Tipo de Retención
        sheet_summary = workbook.add_sheet('Resumen por Tipo', cell_overwrite_ok=True)
        
        # Encabezados
        summary_headers = ['Tipo de Retención', 'Cantidad', 'Base Imponible', 'Monto Retenido', 'Promedio %']
        for col, header in enumerate(summary_headers):
            sheet_summary.write(0, col, header, titulos)
        
        # Agrupar por tipo de retención
        retention_summary = {}
        for invoice in invoices:
            retention_info = self._get_retention_info(invoice)
            retention_type = retention_info['type']
            
            if retention_type not in retention_summary:
                retention_summary[retention_type] = {
                    'count': 0, 'base': 0, 'amount': 0, 'rates': []
                }
            
            retention_summary[retention_type]['count'] += 1
            retention_summary[retention_type]['base'] += retention_info['base']
            retention_summary[retention_type]['amount'] += retention_info['amount']
            retention_summary[retention_type]['rates'].append(retention_info['rate'])
        
        # Escribir datos
        row = 1
        for retention_type, data in retention_summary.items():
            avg_rate = sum(data['rates']) / len(data['rates']) if data['rates'] else 0
            
            sheet_summary.write(row, 0, retention_type, detalle)
            sheet_summary.write(row, 1, data['count'], detalle)
            sheet_summary.write(row, 2, data['base'], detalle_moneda)
            sheet_summary.write(row, 3, data['amount'], detalle_moneda)
            sheet_summary.write(row, 4, f"{avg_rate:.2f}%", detalle)
            row += 1
        
        # Guardar archivo
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['kc_fiscal_hn.retentions_sar.excel'].create(
            {'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        fp.close()
        
        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'kc_fiscal_hn.retentions_sar.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
    
    def get_retentions(self):
        """Obtener retenciones para el reporte"""
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['posted'])
        ]
        
        # Filtrar por tipo de retención
        if self.retention_type == 'isr':
            domain.append(('invoice_line_ids.tax_ids.name', 'ilike', 'ISR'))
        elif self.retention_type == 'isv':
            domain.append(('invoice_line_ids.tax_ids.name', 'ilike', 'ISV'))
        
        return self.env['account.move'].search(domain)
    
    def _get_retention_info(self, invoice):
        """Obtener información de retenciones de una factura"""
        retention_info = {
            'base': 0,
            'type': 'N/A',
            'rate': 0,
            'amount': 0
        }
        
        for line in invoice.invoice_line_ids:
            if line.tax_ids:
                retention_info['base'] += line.price_subtotal
                
                for tax in line.tax_ids:
                    if 'ISR' in tax.name.upper():
                        retention_info['type'] = 'ISR'
                        retention_info['rate'] = tax.amount
                        retention_info['amount'] += tax.amount
                    elif 'ISV' in tax.name.upper():
                        retention_info['type'] = 'ISV'
                        retention_info['rate'] = tax.amount
                        retention_info['amount'] += tax.amount
                    else:
                        retention_info['type'] = 'Otra'
                        retention_info['rate'] = tax.amount
                        retention_info['amount'] += tax.amount
        
        return retention_info
    
    def action_download_excel(self):
        """Descargar archivo Excel"""
        if not self.excel_file:
            raise ValidationError(_('Primero debe generar el reporte'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=excel_filename&download=true',
            'target': 'self',
        }


class ReportRetentionsSarExcel(models.TransientModel):
    _name = 'kc_fiscal_hn.retentions_sar.excel'
    _description = 'Reporte de Retenciones SAR Excel'

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