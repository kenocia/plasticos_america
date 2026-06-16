# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import socket
from datetime import datetime


class PrinterTestWizard(models.TransientModel):
    _name = 'network.printer.test.wizard'
    _description = 'Wizard de Prueba de Conexión de Impresora'

    printer_id = fields.Many2one(
        'network.printer',
        string='Impresora',
        required=True,
        readonly=True
    )
    
    printer_name = fields.Char(
        string='Nombre de Impresora',
        related='printer_id.name',
        readonly=True
    )
    
    ip_address = fields.Char(
        string='Dirección IP',
        related='printer_id.ip_address',
        readonly=True
    )
    
    ping_status = fields.Text(
        string='Estado de Ping',
        readonly=True
    )
    
    port_9100_status = fields.Text(
        string='Puerto 9100 (Raw Printing)',
        readonly=True
    )
    
    port_515_status = fields.Text(
        string='Puerto 515 (LPR)',
        readonly=True
    )
    
    port_631_status = fields.Text(
        string='Puerto 631 (IPP)',
        readonly=True
    )
    
    overall_status = fields.Selection(
        [
            ('success', 'Conexión Exitosa'),
            ('warning', 'Advertencia'),
            ('error', 'Error de Conexión'),
        ],
        string='Estado General',
        readonly=True
    )
    
    test_date = fields.Datetime(
        string='Fecha de Prueba',
        default=lambda self: fields.Datetime.now(),
        readonly=True
    )
    
    print_status = fields.Text(
        string='Estado de Impresión',
        readonly=True
    )
    
    def action_print_test_document(self):
        """Imprimir un documento de prueba en la impresora"""
        self.ensure_one()
        if not self.printer_id:
            raise UserError(_('No se ha seleccionado una impresora.'))
        
        try:
            # Generar documento de prueba
            test_document = self._generate_test_document()
            
            # Enviar a la impresora
            result = self.printer_id.send_raw_print(test_document)
            
            # Actualizar estado
            if result.get('success'):
                self.print_status = _('✓ Documento de prueba enviado exitosamente a %s:%s\n%s') % (
                    self.printer_id.ip_address,
                    result.get('port', 9100),
                    result.get('message', '')
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Impresión Exitosa'),
                        'message': _('El documento de prueba se ha enviado correctamente a la impresora.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.print_status = _('✗ Error al enviar documento: %s') % result.get('error', 'Error desconocido')
                raise UserError(_('Error al imprimir: %s') % result.get('error', 'Error desconocido'))
                
        except Exception as e:
            self.print_status = _('✗ Error: %s') % str(e)
            raise UserError(_('Error al imprimir documento de prueba: %s') % str(e))
    
    def _generate_test_document(self):
        """Generar contenido del documento de prueba"""
        now = datetime.now()
        date_str = now.strftime('%d/%m/%Y %H:%M:%S')
        
        # Obtener el tipo de impresora (Listín o A4 o Carta)
        printer_type_label = dict(self.env['network.printer']._fields['printer_type'].selection).get(
            self.printer_id.printer_type, self.printer_id.printer_type
        )
        
        # Documento de prueba en formato texto simple
        # Para impresoras térmicas, se pueden agregar comandos ESC/POS
        document = f"""
========================================
    DOCUMENTO DE PRUEBA DE IMPRESORA
========================================

Impresora: {self.printer_name}
Dirección IP: {self.ip_address}
Tipo: {printer_type_label}
Fecha y Hora: {date_str}

Este es un documento de prueba para verificar
la conectividad y funcionamiento de la impresora
en red.

Si está leyendo este documento, significa que
la impresora está funcionando correctamente.

========================================
        FIN DEL DOCUMENTO DE PRUEBA
========================================


"""
        return document.encode('utf-8', errors='ignore')

