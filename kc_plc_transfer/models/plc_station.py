# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlcStation(models.Model):
    _name = 'plc.station'
    _description = 'PLC Station'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'station_code'

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    station_code = fields.Char(
        string='Código de Estación',
        required=True,
        tracking=True,
        help='Código único de la estación por compañía',
    )
    mode = fields.Selection(
        [
            ('receiving', 'Receiving'),
            ('reprocess', 'Reproceso'),
        ],
        string='Modo',
        required=True,
        default='receiving',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de Operación',
        required=True,
        domain=[('code', '=', 'internal')],
        tracking=True,
        help='Tipo de operación de traslado interno',
    )
    location_src_id = fields.Many2one(
        'stock.location',
        string='Ubicación Origen',
        tracking=True,
        help='Ubicación origen (requerida para modo receiving)',
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación Destino',
        required=True,
        tracking=True,
    )
    auto_validate = fields.Boolean(
        string='Validar Automáticamente',
        required=True,
        default=True,
        tracking=True,
        help='Validar automáticamente los traslados',
    )
    require_sensor_confirm = fields.Boolean(
        string='Requiere Confirmación de Sensor',
        required=True,
        default=False,
        tracking=True,
        help='Feature flag para confirmación por sensor (no implementado aún)',
    )
    allowed_source_parent_id = fields.Many2one(
        'stock.location',
        string='Ubicación Padre Permitida',
        tracking=True,
        help='Para modo reproceso: limita origen al árbol de esta ubicación',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True,
    )
    api_key = fields.Char(
        string='API Key',
        required=True,
        help='Clave API para autenticación del endpoint REST',
    )

    _sql_constraints = [
        (
            'unique_station_code_company',
            'UNIQUE(station_code, company_id)',
            'El código de estación debe ser único por compañía',
        ),
    ]

    @api.constrains('mode', 'location_src_id')
    def _check_receiving_location_src(self):
        """Si mode=receiving => location_src_id obligatorio"""
        for record in self:
            if record.mode == 'receiving' and not record.location_src_id:
                raise ValidationError(
                    'La ubicación origen es obligatoria para el modo Receiving'
                )

    @api.constrains('location_dest_id')
    def _check_location_dest(self):
        """location_dest_id debe existir siempre"""
        for record in self:
            if not record.location_dest_id:
                raise ValidationError('La ubicación destino es obligatoria')
