# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PlcEventLog(models.Model):
    _name = 'plc.event.log'
    _description = 'PLC Event Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'timestamp desc'

    event_uuid = fields.Char(
        string='UUID del Evento',
        required=True,
        index=True,
        tracking=True,
        help='UUID único del evento para control de idempotencia',
    )
    station_id = fields.Many2one(
        'plc.station',
        string='Estación',
        required=True,
        index=True,
        tracking=True,
        ondelete='restrict',
    )
    timestamp = fields.Datetime(
        string='Fecha/Hora',
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
    )
    qr_raw = fields.Char(
        string='QR Raw',
        required=True,
        tracking=True,
        help='Código QR leído sin procesar',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        index=True,
        tracking=True,
        ondelete='set null',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        tracking=True,
        ondelete='set null',
    )
    state = fields.Selection(
        [
            ('pending', 'Pendiente'),
            ('success', 'Éxito'),
            ('rejected', 'Rechazado'),
            ('error', 'Error'),
            ('duplicate', 'Duplicado'),
            ('timeout', 'Timeout'),
        ],
        string='Estado',
        required=True,
        default='pending',
        index=True,
        tracking=True,
    )
    reason_code = fields.Selection(
        [
            ('LOT_NOT_FOUND', 'Lote No Encontrado'),
            ('INVALID_QR_FORMAT', 'Formato QR Inválido'),
            ('NO_STOCK', 'Sin Stock'),
            ('WRONG_LOCATION', 'Ubicación Incorrecta'),
            ('LOT_SPLIT_MULTIPLE_LOCATIONS', 'Lote Dividido en Múltiples Ubicaciones'),
            ('SOURCE_NOT_ALLOWED', 'Origen No Permitido'),
            ('DUPLICATE', 'Duplicado'),
            ('ODOO_EXCEPTION', 'Excepción Odoo'),
            ('SENSOR_TIMEOUT', 'Timeout de Sensor'),
        ],
        string='Código de Razón',
        tracking=True,
    )
    reason_message = fields.Text(
        string='Mensaje de Razón',
        tracking=True,
    )
    from_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Origen',
        tracking=True,
        ondelete='set null',
    )
    to_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Destino',
        tracking=True,
        ondelete='set null',
    )
    qty = fields.Float(
        string='Cantidad',
        tracking=True,
        digits='Product Unit of Measure',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Traslado',
        tracking=True,
        ondelete='set null',
    )
    attempts = fields.Integer(
        string='Intentos',
        required=True,
        default=1,
        tracking=True,
    )
    processed_at = fields.Datetime(
        string='Procesado En',
        tracking=True,
    )
    payload_json = fields.Text(
        string='Payload JSON',
        help='Payload completo recibido del PLC/Gateway',
    )
    response_json = fields.Text(
        string='Response JSON',
        help='Respuesta completa enviada al PLC/Gateway',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='station_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    picking_count = fields.Integer(
        string='Cantidad de Traslados',
        compute='_compute_picking_count',
    )

    @api.depends('picking_id')
    def _compute_picking_count(self):
        """Calcular cantidad de traslados para smart button"""
        for record in self:
            record.picking_count = 1 if record.picking_id else 0

    def action_view_picking(self):
        """Abrir el traslado relacionado"""
        self.ensure_one()
        if not self.picking_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Traslado',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    _sql_constraints = [
        (
            'unique_event_uuid_company',
            'UNIQUE(event_uuid, company_id)',
            'El UUID del evento debe ser único por compañía',
        ),
    ]

    def _auto_init(self):
        """Crear índices compuestos según spec"""
        res = super()._auto_init()
        # Crear índices compuestos si no existen
        # Índice compuesto: (station_id, timestamp)
        self.env.cr.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = %s 
            AND indexname = 'plc_event_log_station_timestamp_idx'
        """, (self._table,))
        if not self.env.cr.fetchone():
            self.env.cr.execute("""
                CREATE INDEX plc_event_log_station_timestamp_idx 
                ON {} (station_id, timestamp DESC)
            """.format(self._table))
            _logger.info("Created index plc_event_log_station_timestamp_idx")
        
        # Índice compuesto: (lot_id, state)
        self.env.cr.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = %s 
            AND indexname = 'plc_event_log_lot_state_idx'
        """, (self._table,))
        if not self.env.cr.fetchone():
            self.env.cr.execute("""
                CREATE INDEX plc_event_log_lot_state_idx 
                ON {} (lot_id, state)
            """.format(self._table))
            _logger.info("Created index plc_event_log_lot_state_idx")
        
        return res

    @api.constrains('event_uuid', 'company_id')
    def _check_unique_event_uuid(self):
        """Validar unicidad de event_uuid por compañía"""
        for record in self:
            existing = self.search([
                ('event_uuid', '=', record.event_uuid),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id),
            ], limit=1)
            if existing:
                raise ValidationError(
                    f'Ya existe un evento con UUID {record.event_uuid} '
                    f'para la compañía {record.company_id.name}'
                )
