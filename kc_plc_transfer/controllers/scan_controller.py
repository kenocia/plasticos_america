# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ScanController(http.Controller):
    """
    Controlador REST para recibir escaneos de QR desde PLC/Gateway
    """

    def _validate_api_key(self, api_key):
        """
        Validar API Key contra las estaciones activas
        Retorna la estación si la clave es válida, None en caso contrario
        """
        if not api_key:
            return None
        
        station = request.env['plc.station'].sudo().search([
            ('api_key', '=', api_key),
            ('active', '=', True),
        ], limit=1)
        
        return station if station else None

    def _validate_payload(self, payload):
        """
        Validar que el payload tenga los campos obligatorios
        """
        required_fields = ['event_uuid', 'station_code', 'qr']
        missing_fields = [field for field in required_fields if field not in payload or not payload[field]]
        
        if missing_fields:
            return False, f"Campos obligatorios faltantes: {', '.join(missing_fields)}"
        
        return True, None

    def _check_idempotency(self, event_uuid, company_id):
        """
        Verificar idempotencia por event_uuid
        Retorna el evento existente si ya fue procesado exitosamente o es duplicado
        """
        existing_event = request.env['plc.event.log'].sudo().search([
            ('event_uuid', '=', event_uuid),
            ('company_id', '=', company_id),
        ], limit=1)
        
        if existing_event and existing_event.state in ('success', 'duplicate'):
            return existing_event
        
        return None

    @http.route('/api/scan/transfer', type='http', auth='none', methods=['POST'], csrf=False)
    def scan_transfer(self, **kwargs):
        """
        Endpoint REST para recibir escaneos de QR desde PLC/Gateway
        
        Headers requeridos:
        - X-API-Key: Clave API de la estación
        - Content-Type: application/json
        
        Payload JSON requerido:
        {
            "event_uuid": "<uuid>",
            "station_code": "RCV-01",
            "qr": "LOT:ABC123"
        }
        
        Returns JSON con:
        {
            "status": "success|rejected|duplicate|error",
            "code": "reason_code (si aplica)",
            "message": "mensaje descriptivo",
            "picking_id": <id> (si aplica),
            "lot": <lot_name> (si aplica),
            "product": <product_name> (si aplica),
            "qty": <cantidad> (si aplica),
            "from_location": <location_name> (si aplica),
            "to_location": <location_name> (si aplica)
        }
        """
        try:
            # Obtener API Key del header
            api_key = request.httprequest.headers.get('X-API-Key')
            
            if not api_key:
                response_data = {
                    'status': 'error',
                    'code': None,
                    'message': 'Header X-API-Key requerido',
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=401
                )
            
            # Validar API Key
            station = self._validate_api_key(api_key)
            if not station:
                response_data = {
                    'status': 'error',
                    'code': None,
                    'message': 'API Key inválida o estación inactiva',
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=403
                )
            
            # Obtener payload JSON del body
            try:
                payload = json.loads(request.httprequest.data.decode('utf-8'))
            except (json.JSONDecodeError, AttributeError, UnicodeDecodeError) as e:
                response_data = {
                    'status': 'error',
                    'code': None,
                    'message': f'Error al parsear JSON: {str(e)}',
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            # Validar payload
            is_valid, error_msg = self._validate_payload(payload)
            if not is_valid:
                response_data = {
                    'status': 'error',
                    'code': None,
                    'message': error_msg,
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            event_uuid = payload.get('event_uuid')
            station_code = payload.get('station_code')
            qr = payload.get('qr')
            
            # Validar que el station_code coincida con la estación autenticada
            if station.station_code != station_code:
                response_data = {
                    'status': 'error',
                    'code': None,
                    'message': f'station_code no coincide con la estación autenticada',
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            # Verificar idempotencia
            duplicate_event = self._check_idempotency(event_uuid, station.company_id.id)
            if duplicate_event:
                response_data = {
                    'status': 'duplicate',
                    'code': 'DUPLICATE',
                    'message': f'Evento {event_uuid} ya fue procesado anteriormente',
                }
                if duplicate_event.picking_id:
                    response_data['picking_id'] = duplicate_event.picking_id.id
                
                # Guardar respuesta en el evento existente
                duplicate_event.write({
                    'response_json': json.dumps(response_data),
                })
                
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=200
                )
            
            # Crear registro de evento con state=pending
            event_log = request.env['plc.event.log'].sudo().create({
                'event_uuid': event_uuid,
                'station_id': station.id,
                'qr_raw': qr,
                'state': 'pending',
                'payload_json': json.dumps(payload),
            })
            
            # Respuesta inicial pendiente
            response_data = {
                'status': 'pending',
                'code': None,
                'message': f'Evento {event_uuid} registrado correctamente, pendiente de procesamiento',
            }
            
            # Guardar respuesta inicial
            event_log.write({
                'response_json': json.dumps(response_data),
            })
            
            _logger.info(f"Evento {event_uuid} creado en estado pending para estación {station_code}")
            
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )
            
        except Exception as e:
            _logger.error(f"Error en scan_transfer: {str(e)}", exc_info=True)
            
            # Intentar crear registro de error si tenemos datos mínimos
            try:
                event_uuid = payload.get('event_uuid', 'UNKNOWN') if 'payload' in locals() else 'UNKNOWN'
                station_id = station.id if 'station' in locals() and station else False
                qr_raw = payload.get('qr', '') if 'payload' in locals() else ''
                payload_json = json.dumps(payload) if 'payload' in locals() else ''
                
                request.env['plc.event.log'].sudo().create({
                    'event_uuid': event_uuid,
                    'station_id': station_id,
                    'qr_raw': qr_raw,
                    'state': 'error',
                    'reason_code': 'ODOO_EXCEPTION',
                    'reason_message': str(e),
                    'payload_json': payload_json,
                })
            except Exception as log_error:
                _logger.error(f"Error al crear log de error: {str(log_error)}")
            
            response_data = {
                'status': 'error',
                'code': 'ODOO_EXCEPTION',
                'message': f'Error interno del servidor: {str(e)}',
            }
            
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
