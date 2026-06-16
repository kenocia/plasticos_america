# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class KcGs1PickingScanLog(models.Model):
    _name = 'kc.gs1.picking.scan.log'
    _description = 'Registro de escaneos GS1 en operaciones de inventario'
    _order = 'session_line_no desc, scan_date desc, id desc'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Operación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        ondelete='restrict',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        required=True,
        ondelete='restrict',
    )
    qty = fields.Float(
        string='Cantidad',
        required=True,
        digits='Product Unit of Measure',
    )
    barcode_raw = fields.Text(
        string='QR escaneado',
        required=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True,
    )
    scan_date = fields.Datetime(
        string='Fecha de escaneo',
        default=fields.Datetime.now,
        required=True,
    )
    scan_session_uid = fields.Char(
        string='Sesión wizard',
        index=True,
        help='Identificador de la sesión del wizard GS1 que registró el escaneo.',
    )
    session_line_no = fields.Integer(
        string='Línea rampa',
        readonly=True,
        index=True,
        help='Correlativo por rampa (sesión). El más reciente tiene el número mayor.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('session_line_no') and vals.get('scan_session_uid'):
                domain = [('scan_session_uid', '=', vals['scan_session_uid'])]
                if vals.get('picking_id'):
                    domain.append(('picking_id', '=', vals['picking_id']))
                vals['session_line_no'] = self.search_count(domain) + 1
        return super().create(vals_list)

    @api.constrains('picking_id', 'lot_id', 'barcode_raw', 'scan_session_uid')
    def _check_duplicate_scan(self):
        for log in self:
            picking_type = log.picking_id.picking_type_id
            if not picking_type.kc_gs1_block_duplicate_scan:
                continue
            domain_base = [
                ('picking_id', '=', log.picking_id.id),
                ('id', '!=', log.id),
            ]
            if log.scan_session_uid:
                domain_base.append(('scan_session_uid', '=', log.scan_session_uid))
            if self.search(domain_base + [('lot_id', '=', log.lot_id.id)], limit=1):
                raise ValidationError(
                    _('Este QR/lote ya fue escaneado en esta operación.')
                )
            if self.search(domain_base + [('barcode_raw', '=', log.barcode_raw)], limit=1):
                raise ValidationError(
                    _('Este QR/lote ya fue escaneado en esta operación.')
                )
