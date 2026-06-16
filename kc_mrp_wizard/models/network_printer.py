# -*- coding: utf-8 -*-

import logging
import socket

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NetworkPrinter(models.Model):
    _inherit = 'network.printer'

    def send_tcp_raw_binary(self, data, port=None, timeout=30):
        """Binario tal cual por TCP (ZPL/Zebra en puerto 9100), sin ESC/POS ni form feed."""
        self.ensure_one()
        if not self.ip_address:
            raise UserError(_('La impresora no tiene una dirección IP configurada.'))
        if isinstance(data, str):
            data = data.encode('utf-8', errors='replace')
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        use_port = port or 9100
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.ip_address, use_port))
            sock.sendall(data)
            sock.close()
            _logger.info(
                'KC MRP: RAW binario enviado %s bytes a %s:%s',
                len(data), self.ip_address, use_port,
            )
            return {
                'success': True,
                'message': _('Datos enviados correctamente (TCP binario)'),
                'port': use_port,
                'bytes_sent': len(data),
            }
        except socket.timeout:
            return {
                'success': False,
                'error': _('Timeout al enviar a la impresora (%s:%s)') % (self.ip_address, use_port),
                'port': use_port,
            }
        except OSError as e:
            return {
                'success': False,
                'error': _('Error de red: %s') % str(e),
                'port': use_port,
            }
        except Exception as e:
            _logger.exception('send_tcp_raw_binary')
            return {
                'success': False,
                'error': _('Error inesperado: %s') % str(e),
                'port': use_port,
            }
