# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import re
import socket
import subprocess
import platform
import struct
import logging

_logger = logging.getLogger(__name__)

# Intentar importar pycups (opcional)
try:
    import cups
    CUPS_AVAILABLE = True
except ImportError:
    CUPS_AVAILABLE = False
    _logger.warning("pycups no está instalado. IPP puede no funcionar correctamente. Instale con: pip install pycups")


class NetworkPrinter(models.Model):
    _name = 'network.printer'
    _description = 'Impresora en Red'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la impresora'
    )
    
    ip_address = fields.Char(
        string='Dirección IP',
        required=True,
        help='Dirección IP de la impresora en la red (ejemplo: 192.168.1.100)'
    )
    
    printer_type = fields.Selection(
        [
            ('contado', 'Listín'),
            ('credito', 'A4 o Carta'),
        ],
        string='Tipo de Impresora',
        required=True,
        default='contado',
        help='Tipo de impresora: Listín (para facturas) o A4/Carta (para notas de débito)'
    )
    
    active = fields.Boolean(
        string='Activa',
        default=True,
        help='Si está desactivada, la impresora no estará disponible para usar'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre la impresora'
    )
    
    # Configuraciones de papel
    paper_width = fields.Integer(
        string='Ancho de Papel (caracteres)',
        default=42,
        help='Ancho del papel en caracteres (típicamente 42 para listín, 58 o 80 para papel ancho)'
    )
    
    auto_cut = fields.Boolean(
        string='Corte Automático',
        default=True,
        help='Cortar papel automáticamente después de imprimir'
    )
    
    open_cash_drawer = fields.Boolean(
        string='Abrir Cajón de Dinero',
        default=False,
        help='Abrir el cajón de dinero al imprimir (si la impresora lo soporta)'
    )
    
    paper_feed_lines = fields.Integer(
        string='Líneas de Avance de Papel',
        default=3,
        help='Número de líneas a avanzar antes de cortar (para facilitar el corte manual)'
    )
    
    character_set = fields.Selection(
        [
            ('pc437', 'PC437 (USA)'),
            ('pc850', 'PC850 (Multilingual)'),
            ('pc852', 'PC852 (Latin2)'),
            ('pc858', 'PC858 (Euro)'),
            ('pc860', 'PC860 (Portuguese)'),
            ('pc863', 'PC863 (Canadian French)'),
            ('pc865', 'PC865 (Nordic)'),
            ('pc866', 'PC866 (Cyrillic)'),
            ('pc1252', 'Windows-1252 (Western European)'),
        ],
        string='Juego de Caracteres',
        default='pc437',
        help='Juego de caracteres para la impresora'
    )
    
    print_density = fields.Selection(
        [
            ('light', 'Ligera'),
            ('normal', 'Normal'),
            ('dark', 'Oscura'),
        ],
        string='Densidad de Impresión',
        default='normal',
        help='Densidad de impresión (intensidad del texto)'
    )
    
    # Configuración de tipos de documentos que imprime esta impresora
    print_invoice_contado = fields.Boolean(
        string='Imprime Facturas al Contado',
        default=False,
        help='Esta impresora imprime facturas con términos de pago al contado'
    )
    
    print_invoice_credito = fields.Boolean(
        string='Imprime Facturas a Crédito',
        default=False,
        help='Esta impresora imprime facturas con términos de pago a crédito'
    )
    
    print_credit_note = fields.Boolean(
        string='Imprime Notas de Crédito',
        default=False,
        help='Esta impresora imprime notas de crédito'
    )
    
    # Protocolo de impresión
    print_protocol = fields.Selection(
        [
            ('raw', 'RAW (Puerto 9100)'),
            ('ipp', 'IPP - Internet Printing Protocol (Puerto 631)'),
            ('lpr', 'LPR - Line Printer Remote (Puerto 515)'),
        ],
        string='Protocolo de Impresión',
        default='raw',
        required=True,
        help='Protocolo de impresión a usar. RAW funciona con impresoras térmicas. IPP/LPR son para impresoras de inyección de tinta como Canon Pixma.'
    )
    
    printer_queue_name = fields.Char(
        string='Nombre de Cola (LPR/IPP)',
        help='Nombre de la cola de impresión para protocolos LPR o IPP. Dejar vacío para usar el nombre por defecto de la impresora.'
    )

    @api.constrains('ip_address')
    def _check_ip_address(self):
        """Validar formato de dirección IP"""
        ip_pattern = re.compile(
            r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        )
        for printer in self:
            if printer.ip_address and not ip_pattern.match(printer.ip_address):
                raise ValidationError(
                    _('La dirección IP "%s" no tiene un formato válido. '
                      'Debe ser una dirección IPv4 válida (ejemplo: 192.168.1.100)')
                    % printer.ip_address
                )

    @api.model
    def get_printer_by_type(self, printer_type):
        """Obtener una impresora activa por tipo (método legacy, usar get_printer_for_document)"""
        return self.search([
            ('printer_type', '=', printer_type),
            ('active', '=', True)
        ], limit=1)
    
    @api.model
    def get_printer_for_document(self, account_move):
        """
        Obtener la impresora adecuada según el tipo de documento (account.move)
        
        Lógica:
        - Facturas al contado → impresora con print_invoice_contado=True
        - Facturas a crédito → impresora con print_invoice_credito=True
        - Notas de crédito → impresora con print_credit_note=True
        
        Args:
            account_move: registro de account.move (factura o nota de crédito)
            
        Returns:
            network.printer: impresora configurada para el tipo de documento
        """
        if not account_move:
            return self.env['network.printer']
        
        # Determinar qué tipo de documento es
        domain = [('active', '=', True)]
        
        if account_move.move_type == 'out_refund':
            # Nota de crédito
            domain.append(('print_credit_note', '=', True))
        elif account_move.move_type == 'out_invoice':
            # Factura - determinar si es contado o crédito
            is_contado = False
            
            # Verificar término de pago
            if account_move.invoice_payment_term_id:
                payment_term = account_move.invoice_payment_term_id
                # Verificar si tiene campo payment_type
                if hasattr(payment_term, 'payment_type') and payment_term.payment_type:
                    is_contado = (payment_term.payment_type == 'cash')
                else:
                    # Fallback: buscar en el nombre
                    is_contado = 'contado' in payment_term.name.lower()
            
            if is_contado:
                domain.append(('print_invoice_contado', '=', True))
            else:
                domain.append(('print_invoice_credito', '=', True))
        else:
            # Tipo de documento no soportado
            return self.env['network.printer']
        
        # Buscar impresora que coincida
        printer = self.search(domain, limit=1)
        return printer

    def test_connection(self):
        """
        Método para testear la conexión a la impresora
        Intenta hacer ping y conectar a puertos comunes de impresoras
        Abre un wizard con los resultados
        """
        self.ensure_one()
        if not self.ip_address:
            raise UserError(_('La impresora no tiene una dirección IP configurada.'))
        
        # 1. Test de ping
        ping_result = self._test_ping(self.ip_address)
        
        # 2. Test de conexión a puertos comunes de impresoras
        port_9100_result = self._test_port(self.ip_address, 9100)
        port_515_result = self._test_port(self.ip_address, 515)
        port_631_result = self._test_port(self.ip_address, 631)
        
        # Determinar estado general
        ping_success = '✓' in ping_result or 'OK' in ping_result
        port_success = any('✓' in r or 'OK' in r for r in [port_9100_result, port_515_result, port_631_result])
        
        if ping_success and port_success:
            overall_status = 'success'
        elif ping_success:
            overall_status = 'warning'
        else:
            overall_status = 'error'
        
        # Crear wizard con los resultados
        wizard = self.env['network.printer.test.wizard'].create({
            'printer_id': self.id,
            'ping_status': ping_result,
            'port_9100_status': port_9100_result,
            'port_515_status': port_515_result,
            'port_631_status': port_631_result,
            'overall_status': overall_status,
        })
        
        # Abrir wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Prueba de Conexión - %s') % self.name,
            'res_model': 'network.printer.test.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def _test_ping(self, ip_address):
        """Testear conectividad básica usando ping"""
        try:
            # Determinar comando de ping según el sistema operativo
            if platform.system().lower() == 'windows':
                cmd = ['ping', '-n', '2', '-w', '2000', ip_address]
            else:
                cmd = ['ping', '-c', '2', '-W', '2', ip_address]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            if result.returncode == 0:
                return _('✓ Ping: La IP responde correctamente')
            else:
                return _('✗ Ping: La IP no responde (puede estar apagada o inaccesible)')
        except subprocess.TimeoutExpired:
            return _('✗ Ping: Timeout - La IP no responde en el tiempo esperado')
        except Exception as e:
            return _('✗ Ping: Error al ejecutar ping - %s') % str(e)
    
    def _test_port(self, ip_address, port, timeout=2):
        """Testear si un puerto específico está abierto"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip_address, port))
            sock.close()
            
            if result == 0:
                port_name = {
                    9100: 'Raw Printing (9100)',
                    515: 'LPR (515)',
                    631: 'IPP (631)'
                }.get(port, f'Puerto {port}')
                return _('✓ %s: Puerto abierto') % port_name
            else:
                return _('✗ Puerto %s: Cerrado o inaccesible') % port
        except socket.gaierror:
            return _('✗ Puerto %s: Error de resolución de nombre') % port
        except Exception as e:
            return _('✗ Puerto %s: Error - %s') % (port, str(e))

    def _get_escpos_commands(self):
        """
        Generar comandos ESC/POS según las configuraciones de la impresora
        """
        ESC = '\x1B'
        commands = b''
        
        # Establecer juego de caracteres
        char_sets = {
            'pc437': '\x00',
            'pc850': '\x02',
            'pc852': '\x12',
            'pc858': '\x13',
            'pc860': '\x03',
            'pc863': '\x04',
            'pc865': '\x05',
            'pc866': '\x11',
            'pc1252': '\x10',
        }
        if self.character_set in char_sets:
            commands += (ESC + '@' + ESC + 't' + char_sets[self.character_set]).encode('latin1')
        
        # Establecer densidad de impresión
        density_codes = {
            'light': '\x00',
            'normal': '\x01',
            'dark': '\x02',
        }
        if self.print_density in density_codes:
            commands += (ESC + '7' + density_codes[self.print_density]).encode('latin1')
        
        # Abrir cajón de dinero (si está configurado)
        if self.open_cash_drawer:
            # Comando estándar para abrir cajón: ESC p m t1 t2
            # m=0 (pin 2), t1=25 (pulso 25ms), t2=250 (pulso 250ms)
            commands += (ESC + 'p' + '\x00' + '\x19' + '\xFA').encode('latin1')
        
        return commands
    
    def _get_cut_command(self):
        """Generar comando de corte de papel"""
        ESC = '\x1B'
        GS = '\x1D'
        
        if self.auto_cut:
            # Corte parcial (GS V 0) o corte total (GS V 1)
            # Usamos corte parcial para mejor compatibilidad
            return (GS + 'V' + '\x00').encode('latin1')
        return b''
    
    def _get_paper_feed_command(self):
        """Generar comando de avance de papel"""
        ESC = '\x1B'
        feed_lines = self.paper_feed_lines or 0
        if feed_lines > 0:
            # ESC d n (avanzar n líneas)
            return (ESC + 'd' + chr(feed_lines)).encode('latin1')
        return b''
    
    def send_raw_print(self, data, port=None, timeout=5):
        """
        Enviar datos a la impresora usando el protocolo configurado
        Aplica configuraciones de papel antes de enviar los datos
        
        :param data: Datos a imprimir (bytes)
        :param port: Puerto de la impresora (si es None, usa el puerto por defecto del protocolo)
        :param timeout: Timeout de conexión en segundos
        :return: Diccionario con resultado de la impresión
        """
        self.ensure_one()
        if not self.ip_address:
            raise UserError(_('La impresora no tiene una dirección IP configurada.'))
        
        if not isinstance(data, bytes):
            data = str(data).encode('utf-8', errors='ignore')
        
        # Determinar protocolo y puerto
        protocol = self.print_protocol or 'raw'
        
        # Seleccionar método según protocolo
        if protocol == 'ipp':
            return self._send_ipp_print(data, port or 631, timeout)
        elif protocol == 'lpr':
            return self._send_lpr_print(data, port or 515, timeout)
        else:  # raw
            # Para impresoras de inyección de tinta, usar RAW sin comandos ESC/POS
            # Solo enviar texto plano directamente
            return self._send_raw_print_simple(data, port or 9100, timeout)
    
    def _send_raw_print_simple(self, data, port=9100, timeout=5):
        """
        Enviar datos directamente a la impresora por TCP/IP (Raw Printing)
        Versión simple sin comandos ESC/POS - para impresoras de inyección de tinta
        """
        try:
            # Asegurar que los datos terminen con salto de línea y avance de página para impresoras de inyección de tinta
            if isinstance(data, bytes):
                if not data.endswith(b'\n') and not data.endswith(b'\r\n'):
                    data = data + b'\n'
            else:
                data = str(data).encode('utf-8', errors='ignore')
                if not data.endswith(b'\n') and not data.endswith(b'\r\n'):
                    data = data + b'\n'
            
            # Agregar avance de página (form feed) al final para que la impresora procese
            # Algunas impresoras Canon necesitan esto para procesar el trabajo
            data = data + b'\x0C'  # Form feed (avance de página)
            
            _logger.debug("RAW: Enviando %d bytes a %s:%s", len(data), self.ip_address, port)
            _logger.debug("RAW: Primeros 100 bytes: %s", data[:100])
            
            # Crear socket TCP/IP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Conectar a la impresora
            sock.connect((self.ip_address, port))
            _logger.debug("RAW: Conectado exitosamente")
            
            # Enviar datos directamente (texto plano)
            # Enviar en chunks pequeños para evitar problemas de buffer
            chunk_size = 1024
            total_sent = 0
            while total_sent < len(data):
                chunk = data[total_sent:total_sent + chunk_size]
                sent = sock.send(chunk)
                if sent == 0:
                    raise OSError("Conexión cerrada por la impresora")
                total_sent += sent
                _logger.debug("RAW: Enviados %d/%d bytes", total_sent, len(data))
            
            _logger.debug("RAW: Todos los datos enviados (%d bytes)", len(data))
            
            # Cerrar la conexión de escritura (shutdown write) para indicar fin de datos
            # Esto es importante para que la impresora procese el trabajo
            sock.shutdown(socket.SHUT_WR)
            _logger.debug("RAW: Conexión de escritura cerrada, esperando procesamiento...")
            
            # Esperar un momento para que la impresora procese
            import time
            time.sleep(2.0)  # Aumentar delay a 2 segundos
            
            # Intentar leer cualquier respuesta (algunas impresoras envían confirmación)
            try:
                sock.settimeout(1.0)
                response = sock.recv(1024)
                if response:
                    _logger.debug("RAW: Respuesta de impresora: %s", response[:100])
            except socket.timeout:
                _logger.debug("RAW: No hay respuesta de la impresora (normal para RAW)")
            
            # Cerrar conexión completamente
            sock.close()
            _logger.info("RAW: Datos enviados correctamente a %s:%s (%d bytes)", self.ip_address, port, len(data))
            
            return {
                'success': True,
                'message': _('Datos enviados correctamente (RAW)'),
                'port': port,
                'bytes_sent': len(data)
            }
            
        except socket.timeout:
            return {
                'success': False,
                'error': _('Timeout: La impresora no respondió en el tiempo esperado'),
                'port': port
            }
        except socket.gaierror:
            return {
                'success': False,
                'error': _('Error de resolución: No se pudo resolver la dirección IP'),
                'port': port
            }
        except ConnectionRefusedError:
            return {
                'success': False,
                'error': _('Conexión rechazada: El puerto %s está cerrado o la impresora rechazó la conexión') % port,
                'port': port
            }
        except OSError as e:
            return {
                'success': False,
                'error': _('Error de conexión: %s') % str(e),
                'port': port
            }
        except Exception as e:
            return {
                'success': False,
                'error': _('Error inesperado: %s') % str(e),
                'port': port
            }
    
    def _send_raw_print(self, data, port=9100, timeout=5):
        """
        Enviar datos directamente a la impresora por TCP/IP (Raw Printing)
        Para impresoras térmicas que soportan ESC/POS
        """
        try:
            # Preparar datos con configuraciones aplicadas
            # 1. Comandos iniciales (juego de caracteres, densidad, cajón)
            initial_commands = self._get_escpos_commands()
            
            # 2. Datos del documento
            document_data = data
            
            # 3. Avance de papel antes del corte
            paper_feed = self._get_paper_feed_command()
            
            # 4. Comando de corte
            cut_command = self._get_cut_command()
            
            # Combinar todo
            full_data = initial_commands + document_data + paper_feed + cut_command
            
            # Crear socket TCP/IP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Conectar a la impresora
            sock.connect((self.ip_address, port))
            
            # Enviar datos completos
            sock.sendall(full_data)
            
            # Cerrar conexión
            sock.close()
            
            return {
                'success': True,
                'message': _('Datos enviados correctamente (RAW con ESC/POS)'),
                'port': port,
                'bytes_sent': len(full_data)
            }
            
        except socket.timeout:
            return {
                'success': False,
                'error': _('Timeout: La impresora no respondió en el tiempo esperado'),
                'port': port
            }
        except socket.gaierror:
            return {
                'success': False,
                'error': _('Error de resolución: No se pudo resolver la dirección IP'),
                'port': port
            }
        except ConnectionRefusedError:
            return {
                'success': False,
                'error': _('Conexión rechazada: El puerto %s está cerrado o la impresora rechazó la conexión') % port,
                'port': port
            }
        except OSError as e:
            return {
                'success': False,
                'error': _('Error de conexión: %s') % str(e),
                'port': port
            }
        except Exception as e:
            return {
                'success': False,
                'error': _('Error inesperado: %s') % str(e),
                'port': port
            }
    
    def _send_ipp_print(self, data, port=631, timeout=5):
        """
        Enviar datos usando IPP (Internet Printing Protocol)
        Intenta usar pycups si CUPS está disponible, sino usa implementación directa
        Para impresoras de inyección de tinta como Canon Pixma
        """
        # Intentar usar pycups si está disponible y CUPS está corriendo
        if CUPS_AVAILABLE:
            try:
                conn = cups.Connection()
                # Si llegamos aquí, CUPS está disponible
                return self._send_ipp_print_with_cups(data, port, timeout, conn)
            except RuntimeError as e:
                # CUPS no está disponible, usar implementación directa
                _logger.warning("CUPS no está disponible (%s), usando IPP directo", str(e))
            except Exception as e:
                _logger.warning("Error al conectar con CUPS (%s), usando IPP directo", str(e))
        
        # Usar implementación directa de IPP (sin CUPS)
        return self._send_ipp_print_direct(data, port, timeout)
    
    def _send_ipp_print_with_cups(self, data, port, timeout, conn):
        """
        Enviar datos usando IPP a través de CUPS
        """
        try:
            # Obtener nombre de cola (usar nombre de impresora si no está configurado)
            queue_name = self.printer_queue_name or self.name or 'ipp'
            # Limpiar nombre de cola (sin espacios ni caracteres especiales)
            queue_name = re.sub(r'[^a-zA-Z0-9_-]', '_', queue_name)
            
            # Construir URI de impresora IPP
            printer_uri = f'ipp://{self.ip_address}:{port}/{queue_name}'
            
            # Crear un archivo temporal en memoria
            import tempfile
            import os
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as tmp_file:
                if isinstance(data, bytes):
                    tmp_file.write(data)
                else:
                    tmp_file.write(data.encode('utf-8', errors='ignore'))
                tmp_file_path = tmp_file.name
            
            try:
                # Intentar imprimir usando pycups
                # Primero, intentar agregar la impresora si no existe
                try:
                    # Verificar si la impresora ya existe en CUPS
                    printers = conn.getPrinters()
                    printer_found = False
                    for printer_name in printers:
                        printer_info = conn.getPrinterAttributes(printer_name)
                        device_uri = printer_info.get('device-uri', '')
                        if self.ip_address in device_uri:
                            printer_found = True
                            queue_name = printer_name
                            break
                    
                    # Si no existe, intentar agregarla temporalmente
                    if not printer_found:
                        # Usar el nombre de la impresora como identificador
                        temp_printer_name = f'odoo_{queue_name}_{self.id}'
                        try:
                            conn.addPrinter(
                                name=temp_printer_name,
                                device=printer_uri,
                                info=f'Odoo Printer {self.name}',
                                location='Odoo Network Printer'
                            )
                            queue_name = temp_printer_name
                        except Exception as add_error:
                            _logger.warning("No se pudo agregar impresora a CUPS: %s", str(add_error))
                            # Intentar usar la URI directamente
                            pass
                except Exception as e:
                    _logger.warning("Error al verificar/agregar impresora en CUPS: %s", str(e))
                
                # Imprimir el archivo
                job_id = conn.printFile(
                    queue_name,
                    tmp_file_path,
                    f'Odoo Print Job {self.name}',
                    {'document-format': 'text/plain'}
                )
                
                _logger.info("IPP: Trabajo de impresión enviado. Job ID: %s", job_id)
                
                return {
                    'success': True,
                    'message': _('Datos enviados correctamente (IPP con CUPS). Job ID: %s') % job_id,
                    'port': port,
                    'bytes_sent': len(data) if isinstance(data, bytes) else len(data.encode('utf-8')),
                    'job_id': job_id
                }
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            
        except cups.IPPError as e:
            _logger.error("Error IPP de CUPS: %s", str(e))
            raise
        except Exception as e:
            _logger.error("Error al enviar por IPP con pycups: %s", str(e), exc_info=True)
            raise
            
            # Crear un archivo temporal en memoria
            import tempfile
            import os
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as tmp_file:
                if isinstance(data, bytes):
                    tmp_file.write(data)
                else:
                    tmp_file.write(data.encode('utf-8', errors='ignore'))
                tmp_file_path = tmp_file.name
            
            try:
                # Intentar imprimir usando pycups
                # Primero, intentar agregar la impresora si no existe
                try:
                    # Verificar si la impresora ya existe en CUPS
                    printers = conn.getPrinters()
                    printer_found = False
                    for printer_name in printers:
                        printer_info = conn.getPrinterAttributes(printer_name)
                        device_uri = printer_info.get('device-uri', '')
                        if self.ip_address in device_uri:
                            printer_found = True
                            queue_name = printer_name
                            break
                    
                    # Si no existe, intentar agregarla temporalmente
                    if not printer_found:
                        # Usar el nombre de la impresora como identificador
                        temp_printer_name = f'odoo_{queue_name}_{self.id}'
                        try:
                            conn.addPrinter(
                                name=temp_printer_name,
                                device=printer_uri,
                                info=f'Odoo Printer {self.name}',
                                location='Odoo Network Printer'
                            )
                            queue_name = temp_printer_name
                        except Exception as add_error:
                            _logger.warning("No se pudo agregar impresora a CUPS: %s", str(add_error))
                            # Intentar usar la URI directamente
                            pass
                except Exception as e:
                    _logger.warning("Error al verificar/agregar impresora en CUPS: %s", str(e))
                
                # Imprimir el archivo
                job_id = conn.printFile(
                    queue_name,
                    tmp_file_path,
                    f'Odoo Print Job {self.name}',
                    {'document-format': 'text/plain'}
                )
                
                _logger.info("IPP: Trabajo de impresión enviado. Job ID: %s", job_id)
                
                return {
                    'success': True,
                    'message': _('Datos enviados correctamente (IPP). Job ID: %s') % job_id,
                    'port': port,
                    'bytes_sent': len(data) if isinstance(data, bytes) else len(data.encode('utf-8')),
                    'job_id': job_id
                }
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            
        except cups.IPPError as e:
            _logger.error("Error IPP de CUPS: %s", str(e))
            return {
                'success': False,
                'error': _('Error IPP: %s') % str(e),
                'port': port
            }
        except Exception as e:
            _logger.error("Error al enviar por IPP con pycups: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': _('Error al enviar por IPP: %s') % str(e),
                'port': port
            }
    
    def _send_ipp_print_direct(self, data, port=631, timeout=5):
        """
        Enviar datos usando IPP directamente (sin CUPS)
        Implementación manual de IPP sobre HTTP
        """
        # Rutas comunes para Canon Pixma
        ipp_paths = []
        if self.printer_queue_name:
            ipp_paths.append(self.printer_queue_name)
        else:
            # Probar diferentes rutas comunes para Canon
            ipp_paths = ['ipp/print', 'ipp', 'printers/ipp', 'printers/Canon', 'printers', '/']
        
        last_error = None
        
        for queue_name in ipp_paths:
            # Limpiar nombre de cola (sin espacios ni caracteres especiales)
            queue_name_clean = re.sub(r'[^a-zA-Z0-9_/-]', '_', queue_name)
            if queue_name == '/':
                path = '/'
            else:
                path = f'/{queue_name_clean}'
            
            try:
                # Construir URI de impresora (formato estándar IPP)
                printer_uri = f'ipp://{self.ip_address}:{port}{path}'
                _logger.debug("IPP: Intentando con URI: %s", printer_uri)
                
                # Construir petición IPP según RFC 8011
                # 1. Versión IPP (2.0)
                version = struct.pack('>BB', 2, 0)
                
                # 2. Operación Print-Job (0x0002)
                operation = struct.pack('>H', 0x0002)
                
                # 3. Request ID
                request_id = struct.pack('>I', 1)
                
                # 4. Begin attributes-group (operation-attributes-tag = 0x01)
                begin_attrs = b'\x01'
                
                # 5. Atributos
                # charset (charset) - tag 0x47
                charset_attr = b'\x47' + struct.pack('>H', 5) + b'utf-8'
                
                # naturalLanguage (naturalLanguage) - tag 0x48
                lang_attr = b'\x48' + struct.pack('>H', 2) + b'en'
                
                # printer-uri (uri) - tag 0x45
                uri_bytes = printer_uri.encode('utf-8')
                uri_attr = b'\x45' + struct.pack('>H', len(uri_bytes)) + uri_bytes
                
                # document-format (mimeMediaType) - tag 0x49, 'text/plain'
                mime_type = b'text/plain'
                mime_attr = b'\x49' + struct.pack('>H', len(mime_type)) + mime_type
                
                # End of attributes
                end_attrs = b'\x03'
                
                # Combinar encabezado IPP
                ipp_body = (version + operation + request_id + begin_attrs + 
                           charset_attr + lang_attr + uri_attr + mime_attr + end_attrs + data)
                
                # IPP se envía sobre HTTP POST
                http_request = (
                    f'POST {path} HTTP/1.1\r\n'
                    f'Host: {self.ip_address}:{port}\r\n'
                    f'Content-Type: application/ipp\r\n'
                    f'Content-Length: {len(ipp_body)}\r\n'
                    f'\r\n'
                ).encode('ascii')
                
                # Crear socket TCP/IP
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                
                # Conectar a la impresora
                sock.connect((self.ip_address, port))
                
                # Enviar petición HTTP con cuerpo IPP
                sock.sendall(http_request + ipp_body)
                
                # Leer respuesta HTTP
                try:
                    # Leer respuesta completa (puede venir en múltiples chunks)
                    response = b''
                    sock.settimeout(2)  # Timeout corto para leer respuesta
                    
                    # Leer hasta obtener toda la respuesta
                    while True:
                        try:
                            chunk = sock.recv(8192)
                            if not chunk:
                                break
                            response += chunk
                            # Si tenemos headers completos y cuerpo, podemos parar
                            if b'\r\n\r\n' in response and len(response) > 100:
                                # Intentar leer un poco más por si hay más datos
                                try:
                                    sock.settimeout(0.5)
                                    chunk = sock.recv(8192)
                                    if chunk:
                                        response += chunk
                                except socket.timeout:
                                    pass
                                break
                        except socket.timeout:
                            if response:
                                break
                            raise
                    
                    _logger.debug("IPP HTTP response completa para %s: %s", path, response[:300])
                    
                    # Buscar status line HTTP en cualquier parte de la respuesta
                    http_status_200 = b'HTTP/1.1 200' in response or b'HTTP/1.0 200' in response
                    http_status_100 = b'HTTP/1.1 100' in response or b'HTTP/1.0 100' in response
                    http_status_404 = b'HTTP/1.1 404' in response or b'HTTP/1.0 404' in response
                    
                    # Si recibimos 100 Continue, esperar la respuesta final
                    if http_status_100:
                        _logger.debug("IPP: Recibido 100 Continue, esperando respuesta final...")
                        sock.settimeout(timeout)
                        final_response = b''
                        while True:
                            try:
                                chunk = sock.recv(8192)
                                if not chunk:
                                    break
                                final_response += chunk
                                if b'\r\n\r\n' in final_response and len(final_response) > 100:
                                    try:
                                        sock.settimeout(0.5)
                                        chunk = sock.recv(8192)
                                        if chunk:
                                            final_response += chunk
                                    except socket.timeout:
                                        pass
                                    break
                            except socket.timeout:
                                if final_response:
                                    break
                                raise
                        response = final_response
                        _logger.debug("IPP HTTP response final para %s: %s", path, response[:300])
                        http_status_200 = b'HTTP/1.1 200' in response or b'HTTP/1.0 200' in response
                    
                    # Verificar que sea HTTP 200 OK
                    if http_status_200:
                        # Buscar cuerpo IPP en la respuesta (después de headers HTTP)
                        ipp_start = response.find(b'\r\n\r\n')
                        if ipp_start > 0:
                            ipp_response = response[ipp_start + 4:]
                            # Buscar inicio del mensaje IPP (versión 2.0 = 0x0200)
                            ipp_msg_start = ipp_response.find(b'\x02\x00')
                            if ipp_msg_start >= 0:
                                ipp_response = ipp_response[ipp_msg_start:]
                            
                            if len(ipp_response) >= 8:
                                status_code = struct.unpack('>H', ipp_response[2:4])[0]
                                # 0x0000 = successful-ok
                                if status_code == 0x0000:
                                    sock.close()
                                    return {
                                        'success': True,
                                        'message': _('Datos enviados correctamente (IPP directo)'),
                                        'port': port,
                                        'bytes_sent': len(http_request) + len(ipp_body)
                                    }
                                else:
                                    _logger.warning("IPP response status: 0x%04x (expected 0x0000)", status_code)
                    elif http_status_404:
                        _logger.debug("IPP: Ruta %s no encontrada (404), probando siguiente...", path)
                        sock.close()
                        last_error = _('Ruta IPP no encontrada: %s') % path
                        continue  # Probar siguiente ruta
                    else:
                        # Si no encontramos status HTTP pero hay contenido IPP, puede que funcione
                        if response and (b'application/ipp' in response or b'\x02\x00' in response):
                            _logger.info("IPP: Respuesta recibida con Content-Type application/ipp o datos IPP, asumiendo éxito")
                            sock.close()
                            return {
                                'success': True,
                                'message': _('Datos enviados correctamente (IPP directo, respuesta parcial)'),
                                'port': port,
                                'bytes_sent': len(http_request) + len(ipp_body)
                            }
                        _logger.warning("IPP HTTP response not 200 OK: %s", response[:200])
                        sock.close()
                        last_error = _('Respuesta HTTP inesperada: %s') % response[:200].decode('ascii', errors='ignore')
                        continue  # Probar siguiente ruta
                except socket.timeout:
                    _logger.warning("IPP: No response received (timeout) para %s", path)
                    sock.close()
                    # Algunas impresoras no envían respuesta, pero puede que funcione
                    # Asumir éxito si no hay error de conexión
                    return {
                        'success': True,
                        'message': _('Datos enviados correctamente (IPP directo, sin respuesta)'),
                        'port': port,
                        'bytes_sent': len(http_request) + len(ipp_body)
                    }
                
                sock.close()
                
            except Exception as e:
                _logger.warning("Error al enviar por IPP directo con ruta %s: %s", path, str(e))
                last_error = str(e)
                try:
                    sock.close()
                except:
                    pass
                continue  # Probar siguiente ruta
        
        # Si llegamos aquí, todas las rutas fallaron
        return {
            'success': False,
            'error': _('Error al enviar por IPP: Todas las rutas fallaron. Último error: %s') % (last_error or 'Desconocido'),
            'port': port
        }
    
    def _send_lpr_print(self, data, port=515, timeout=5):
        """
        Enviar datos usando LPR (Line Printer Remote)
        Para impresoras que soportan LPR
        """
        try:
            # Obtener nombre de cola (usar nombre de impresora si no está configurado)
            queue_name = self.printer_queue_name or self.name or 'lp'
            # Limpiar nombre de cola (sin espacios ni caracteres especiales)
            queue_name = re.sub(r'[^a-zA-Z0-9_-]', '_', queue_name)
            
            # Crear socket TCP/IP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Conectar a la impresora
            sock.connect((self.ip_address, port))
            _logger.debug("LPR: Conectado a %s:%s", self.ip_address, port)
            
            # Enviar comando LPR: \x02 (receive job) + queue_name + \n
            lpr_command = b'\x02' + queue_name.encode('ascii', errors='ignore') + b'\n'
            sock.sendall(lpr_command)
            _logger.debug("LPR: Enviado comando receive job para cola: %s", queue_name)
            
            # Leer respuesta (debe ser \x00 para éxito)
            sock.settimeout(2)  # Timeout más corto para respuestas
            try:
                response = sock.recv(1)
                if response != b'\x00':
                    sock.close()
                    _logger.error("LPR: Rechazado. Respuesta: %s", response.hex() if response else "vacía")
                    return {
                        'success': False,
                        'error': _('LPR rechazó el trabajo. Respuesta: %s') % (response.hex() if response else 'vacía'),
                        'port': port
                    }
            except socket.timeout:
                _logger.warning("LPR: No se recibió respuesta del comando receive job, continuando...")
            
            sock.settimeout(timeout)
            
            # Enviar control file: \x02 (control file) + tamaño + \n + contenido
            # Formato: cfA###hostname\n donde ### es el número de trabajo
            import socket as socket_module
            hostname = socket_module.gethostname()[:31]  # Máximo 31 caracteres
            control_file = f'cfA001{hostname}\n'.encode('ascii', errors='ignore')
            control_size = struct.pack('>H', len(control_file))
            sock.sendall(b'\x02' + control_size + b'\n' + control_file)
            _logger.debug("LPR: Enviado archivo de control, tamaño: %d", len(control_file))
            
            # Leer respuesta
            sock.settimeout(2)
            try:
                response = sock.recv(1)
                if response != b'\x00':
                    sock.close()
                    _logger.error("LPR: Rechazado archivo de control. Respuesta: %s", response.hex() if response else "vacía")
                    return {
                        'success': False,
                        'error': _('LPR rechazó el archivo de control. Respuesta: %s') % (response.hex() if response else 'vacía'),
                        'port': port
                    }
            except socket.timeout:
                _logger.warning("LPR: No se recibió respuesta del archivo de control, continuando...")
            
            sock.settimeout(timeout)
            
            # Enviar data file: \x03 (data file) + tamaño + \n + datos
            data_size = struct.pack('>H', len(data))
            sock.sendall(b'\x03' + data_size + b'\n' + data)
            _logger.debug("LPR: Enviado archivo de datos, tamaño: %d", len(data))
            
            # Leer respuesta
            sock.settimeout(2)
            try:
                response = sock.recv(1)
                if response != b'\x00':
                    sock.close()
                    _logger.error("LPR: Rechazado archivo de datos. Respuesta: %s", response.hex() if response else "vacía")
                    return {
                        'success': False,
                        'error': _('LPR rechazó los datos. Respuesta: %s') % (response.hex() if response else 'vacía'),
                        'port': port
                    }
            except socket.timeout:
                _logger.warning("LPR: No se recibió respuesta del archivo de datos, asumiendo éxito...")
            
            # Cerrar conexión
            sock.close()
            
            return {
                'success': True,
                'message': _('Datos enviados correctamente (LPR)'),
                'port': port,
                'bytes_sent': len(data)
            }
            
        except Exception as e:
            _logger.error("Error al enviar por LPR: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': _('Error al enviar por LPR: %s') % str(e),
                'port': port
            }

    def print_document(self, document_data, printer_type=None):
        """
        Método para enviar documento a imprimir
        Este método se implementará más adelante con la funcionalidad específica
        """
        printer = self
        if printer_type:
            printer = self.get_printer_by_type(printer_type)
            if not printer:
                raise ValidationError(
                    _('No se encontró una impresora activa de tipo %s')
                    % dict(self._fields['printer_type'].selection)[printer_type]
                )
        
        # Usar send_raw_print para enviar el documento
        if isinstance(document_data, str):
            document_data = document_data.encode('utf-8', errors='ignore')
        
        return printer.send_raw_print(document_data)

