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


class ReportSalesSAR(models.TransientModel):
    _name = 'kc_fiscal_hn.wizard.sales_sar'
    _description = 'Reporte de Ventas SAR'

    # Campos para configuración
    date_from = fields.Date(string='Fecha Desde', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.today)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    
    # Campos para filtros
    include_draft = fields.Boolean(string='Incluir Borradores', default=False)
    include_cancelled = fields.Boolean(string='Incluir Canceladas', default=False)
    group_by_tax_rate = fields.Boolean(string='Agrupar por Tasa de Impuesto', default=True)
    group_by_customer_type = fields.Boolean(string='Agrupar por Tipo de Cliente', default=True)
    
    # Campos para resultados
    excel_file = fields.Binary(string='Archivo Excel', readonly=True)
    excel_filename = fields.Char(string='Nombre del Archivo', readonly=True)
    total_invoices = fields.Integer(string='Total Facturas', readonly=True)
    total_amount = fields.Monetary(string='Monto Total', readonly=True, currency_field='currency_id')
    total_isv = fields.Monetary(string='ISV Total', readonly=True, currency_field='currency_id')
    total_exempt = fields.Monetary(string='Exento Total', readonly=True, currency_field='currency_id')
    total_exonerated = fields.Monetary(string='Exonerado Total', readonly=True, currency_field='currency_id')

    def _signed_value(self, invoice, value):
        """Aplicar signo negativo a notas de crédito."""
        sign = -1 if invoice.move_type == 'out_refund' else 1
        return sign * abs(value or 0.0)
    
    def action_generate_report(self):
        """Generar reporte de ventas SAR"""
        self.ensure_one()
        
        # Validar fechas
        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser mayor a la fecha hasta'))
        
        # Buscar facturas en el rango
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id)
        ]
        
        if not self.include_draft:
            domain.append(('state', '!=', 'draft'))
        
        if not self.include_cancelled:
            domain.append(('state', '!=', 'cancel'))
        
        invoices = self.env['account.move'].search(domain)
        
        if not invoices:
            raise ValidationError(_('No se encontraron facturas en el rango de fechas especificado'))
        
        # Generar Excel
        excel_data = self._generate_excel_report(invoices)
        
        # Actualizar campos del wizard
        self.excel_file = base64.b64encode(excel_data)
        self.excel_filename = f'Reporte_Ventas_SAR_{self.date_from}_{self.date_to}.xlsx'
        
        # Calcular totales
        self.total_invoices = len(invoices)
        self.total_amount = sum(self._signed_value(inv, inv.amount_total) for inv in invoices)
        self.total_isv = sum(self._signed_value(inv, inv.isv_total) for inv in invoices)
        self.total_exempt = sum(self._signed_value(inv, inv.amount_exento) for inv in invoices)
        self.total_exonerated = sum(self._signed_value(inv, inv.amount_exonerado) for inv in invoices)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kc_fiscal_hn.wizard.sales_sar',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def print_report(self):
        """Generar reporte de ventas SAR en Excel"""
        if not xlwt:
            raise ValidationError(_('La librería xlwt no está instalada'))
        
        invoices = self.get_invoices()
        filename = f'Reporte_Ventas_SAR_{self.date_from}_{self.date_to}.xls'
        
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
        sheet.write_merge(0, 0, 0, 5, 'REPORTE DE VENTAS SAR - HONDURAS', encabezado)
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
        sheet.write(8, 2, sum(self._signed_value(inv, inv.amount_total) for inv in invoices), detalle_moneda)
        
        sheet.write(9, 0, 'ISV Total', detalle)
        sheet.write(9, 2, sum(self._signed_value(inv, inv.isv_total) for inv in invoices), detalle_moneda)
        
        sheet.write(10, 0, 'Exento Total', detalle)
        sheet.write(10, 2, sum(self._signed_value(inv, inv.amount_exento) for inv in invoices), detalle_moneda)
        
        sheet.write(11, 0, 'Exonerado Total', detalle)
        sheet.write(11, 2, sum(self._signed_value(inv, inv.amount_exonerado) for inv in invoices), detalle_moneda)
        
        # Hoja 2: Detalle por Factura
        sheet_detail = workbook.add_sheet('Detalle por Factura', cell_overwrite_ok=True)
        
        # Encabezados
        headers = [
            'Número Factura', 'Fecha', 'Cliente', 'RTN Cliente', 'Base Imponible',
            'ISV 15%', 'Base 15%', 'ISV 18%', 'Base 18%', 'Exento', 'Exonerado',
            'Descuento', 'Total', 'CAI', 'Estado'
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
            
            # Encabezados
            tax_headers = ['Tasa de Impuesto', 'Cantidad Facturas', 'Base Imponible', 'ISV', 'Total']
            for col, header in enumerate(tax_headers):
                sheet_tax.write(0, col, header, titulos)
            
            # Agrupar por tasa de impuesto
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
            
            # Escribir datos
            row = 1
            for tax_rate, data in tax_summary.items():
                sheet_tax.write(row, 0, tax_rate, detalle)
                sheet_tax.write(row, 1, data['count'], detalle)
                sheet_tax.write(row, 2, data['base'], detalle_moneda)
                sheet_tax.write(row, 3, data['tax'], detalle_moneda)
                sheet_tax.write(row, 4, data['total'], detalle_moneda)
                row += 1
        
        # Hoja 4: Resumen por Tipo de Cliente
        if self.group_by_customer_type:
            sheet_customer = workbook.add_sheet('Resumen por Cliente', cell_overwrite_ok=True)
            
            # Encabezados
            customer_headers = ['Tipo Cliente', 'Cantidad Facturas', 'Base Imponible', 'ISV', 'Total']
            for col, header in enumerate(customer_headers):
                sheet_customer.write(0, col, header, titulos)
            
            # Agrupar por tipo de cliente (con RTN vs sin RTN)
            customer_summary = {
                'Con RTN': {'count': 0, 'base': 0, 'tax': 0, 'total': 0},
                'Sin RTN': {'count': 0, 'base': 0, 'tax': 0, 'total': 0}
            }
            
            for invoice in invoices:
                customer_type = 'Con RTN' if invoice.partner_id.vat else 'Sin RTN'
                customer_summary[customer_type]['count'] += 1
                customer_summary[customer_type]['base'] += self._signed_value(invoice, invoice.base_imponible_total)
                customer_summary[customer_type]['tax'] += self._signed_value(invoice, invoice.isv_total)
                customer_summary[customer_type]['total'] += self._signed_value(invoice, invoice.amount_total)
            
            # Escribir datos
            row = 1
            for customer_type, data in customer_summary.items():
                sheet_customer.write(row, 0, customer_type, detalle)
                sheet_customer.write(row, 1, data['count'], detalle)
                sheet_customer.write(row, 2, data['base'], detalle_moneda)
                sheet_customer.write(row, 3, data['tax'], detalle_moneda)
                sheet_customer.write(row, 4, data['total'], detalle_moneda)
                row += 1
        
        # Guardar archivo
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['kc_fiscal_hn.sales_sar.excel'].create(
            {'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        fp.close()
        
        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'kc_fiscal_hn.sales_sar.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
    
    def get_invoices(self):
        """Obtener facturas para el reporte"""
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id)
        ]
        
        if not self.include_draft:
            domain.append(('state', '!=', 'draft'))
        
        if not self.include_cancelled:
            domain.append(('state', '!=', 'cancel'))
        
        return self.env['account.move'].search(domain)
    
    def action_generate_report(self):
        """Generar reporte de ventas SAR"""
        self.ensure_one()
        
        # Validar fechas
        if self.date_from > self.date_to:
            raise ValidationError(_('La fecha desde no puede ser mayor a la fecha hasta'))
        
        # Obtener facturas
        invoices = self.get_invoices()
        
        if not invoices:
            raise ValidationError(_('No se encontraron facturas en el rango de fechas especificado'))
        
        # Calcular totales
        self.total_invoices = len(invoices)
        self.total_amount = sum(self._signed_value(inv, inv.amount_total) for inv in invoices)
        self.total_isv = sum(self._signed_value(inv, inv.isv_total) for inv in invoices)
        self.total_exempt = sum(self._signed_value(inv, inv.amount_exento) for inv in invoices)
        self.total_exonerated = sum(self._signed_value(inv, inv.amount_exonerado) for inv in invoices)
        
        # Generar Excel
        return self.print_report()
    
    def action_download_excel(self):
        """Descargar archivo Excel"""
        if not self.excel_file:
            raise ValidationError(_('Primero debe generar el reporte'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=excel_file&filename_field=excel_filename&download=true',
            'target': 'self',
        }


class ReportSalesSarExcel(models.TransientModel):
    _name = 'kc_fiscal_hn.sales_sar.excel'
    _description = 'Reporte de Ventas SAR Excel'

    excel_file = fields.Binary('Archivo Excel', readonly=True)
    file_name = fields.Char('Nombre del Archivo', size=64) 