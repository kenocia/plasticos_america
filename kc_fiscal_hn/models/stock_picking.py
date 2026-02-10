# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    sequence_sar_id = fields.Many2one(
        'ir.sequence', string="Secuencia SAR Remisión",
        help="Secuencia para numerar los movimientos de este tipo."
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Campos del módulo original
    sar_name = fields.Char(
        store=True,  # Guarda el valor en la BD
        readonly=False,  # Permite edición manual si es necesario
        index=True,
    )

    cai = fields.Char(string='CAI', help='Clave de Autorización de Impresión')
    fechaLimiteEmision = fields.Datetime(string='Fecha límite de emisión',
                                         help='Fecha límite de emisión de facturas')
    numeroInicial = fields.Char(string='Número inicial',
                                help='Número inicial de facturación', )
    numeroFinal = fields.Char(string='Número final', help='Número final de facturación', )

    motivo_traslado = fields.Selection([
        ('venta', 'Venta'),
        ('importacion', 'Importación'),
        ('consignacion', 'Consignación'),
        ('devolucion', 'Devolución'),
        ('exportacion', 'Exportación'),
        ('traslado_establecimientos', 'Traslado entre establecimientos del contribuyente'),
        ('traslado_transformacion', 'Traslado de bienes para transformación'),
        ('compra', 'Compra'),
        ('rentas', 'Rentas'),
        ('traslado_reparacion', 'Traslado de bienes para reparación'),
        ('traslado_emisor_movil', 'Traslado por venta emisor móvil'),
        ('exhibicion_demostracion', 'Exhibición o demostración'),
        ('participacion_ferias', 'Participación en ferias'),
    ], string="Motivo de Traslado", help="Seleccione el motivo del traslado.")

    transporter_name = fields.Char(string="Nombre del Transportista",
                                   help="Nombre del conductor o empresa transportista")
    transporter_rtn = fields.Char(string="RTN / Identidad",
                                  help="Número de RTN o Identidad del transportista")
    vehicle_info = fields.Char(string="Marca y No. de Placa",
                               help="Marca del vehículo y número de placa")
    driver_license = fields.Char(string="Licencia de Conducir",
                                 help="Número de licencia del conductor")

    # Campos del módulo migrado
    numero_guia = fields.Char(string='Número de Guía', help='Número de guía de remisión')
    fecha_guia = fields.Date(string='Fecha de Guía', default=fields.Date.today)
    transportista = fields.Many2one('res.partner', string='Transportista', 
                                   domain=[('is_company', '=', True)])
    vehiculo = fields.Char(string='Vehículo', help='Número de placa o identificación del vehículo')
    conductor = fields.Char(string='Conductor', help='Nombre del conductor')
    
    # Campos para reportes
    tipo_transporte = fields.Selection([
        ('terrestre', 'Terrestre'),
        ('maritimo', 'Marítimo'),
        ('aereo', 'Aéreo')
    ], string='Tipo de Transporte', default='terrestre')
    
    # Campos calculados
    total_base_imponible = fields.Float(string='Total Base Imponible', 
                                       compute='_compute_totals', store=True)
    total_isv = fields.Float(string='Total ISV', 
                            compute='_compute_totals', store=True)

    def update_custom_fields(self):
        """Función para actualizar la información de numeración y CAI usando sequence_sar_id de stock.picking.type."""
        for record in self:
            picking_type = record.picking_type_id
            if not picking_type or not picking_type.sequence_sar_id:
                raise UserError(_('El tipo de operación no tiene una secuencia SAR asignada.'))

            sequence_sar = picking_type.sequence_sar_id

            if sequence_sar.use_date_range:
                date = record.scheduled_date or fields.Date.today()

                # Obtener el rango de numeración aplicable
                seq_date = self.env['ir.sequence.date_range'].search(
                    [('sequence_id', '=', sequence_sar.id),
                     ('date_from', '<=', date),
                     ('date_to', '>=', date)], limit=1)

                if not seq_date or not seq_date.cai:
                    raise UserError(
                        _('No se encontró rango de numeración o CAI configurado. '
                          'Revise que los rangos de fechas sean correctos y que la información del CAI esté ingresada.'))

                numeroinicial = str(seq_date.rangoInicial).zfill(sequence_sar.padding)
                numeroFinal = str(seq_date.rangoFinal).zfill(sequence_sar.padding)

                record.numeroInicial = sequence_sar.prefix + numeroinicial
                record.numeroFinal = sequence_sar.prefix + numeroFinal
                record.cai = seq_date.cai
                record.fechaLimiteEmision = seq_date.date_to

                # Asignar el valor de sar_name usando la secuencia
                record.sar_name = sequence_sar.next_by_id(sequence_date=record.date_done)

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Información actualizada correctamente",
                'type': 'rainbow_man',
            }
        }

    @api.depends('move_line_ids.base_imponible', 'move_line_ids.monto_isv')
    def _compute_totals(self):
        for picking in self:
            picking.total_base_imponible = sum(picking.move_line_ids.mapped('base_imponible'))
            picking.total_isv = sum(picking.move_line_ids.mapped('monto_isv'))
    
    def action_confirm(self):
        """Sobrescribimos para generar número de guía si es necesario"""
        result = super().action_confirm()
        
        for picking in self:
            if picking.picking_type_code == 'outgoing' and not picking.numero_guia:
                # Generar número de guía para salidas
                sequence = self.env['ir.sequence'].search([
                    ('is_fiscal', '=', True),
                    ('code', '=', 'stock.picking.guide')
                ], limit=1)
                
                if sequence:
                    picking.numero_guia = sequence.next_by_id()
        
        return result