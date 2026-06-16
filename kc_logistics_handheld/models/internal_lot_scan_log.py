# -*- coding: utf-8 -*-

from odoo import api, fields, models


class KcInternalLotScanLog(models.Model):
    _name = 'kc.internal.lot.scan.log'
    _description = 'Log de escaneos GS1 en transferencias internas'
    _order = 'scan_date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'kc.internal.lot.scan.log'
        ) or '/',
    )
    session_name = fields.Char(
        string='Sesión',
        index=True,
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Transferencia',
        ondelete='set null',
        index=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de operación',
        ondelete='set null',
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
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
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
    state = fields.Selection(
        [
            ('scanned', 'Escaneado'),
            ('transferred', 'Transferido'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado',
        default='scanned',
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = seq.next_by_code('kc.internal.lot.scan.log') or '/'
        return super().create(vals_list)
