# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class KcInternalLotScanSession(models.Model):
    _name = 'kc.internal.lot.scan.session'
    _description = 'Sesión de escaneo interno GS1'
    _order = 'created_date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'kc.internal.lot.scan.session'
        ) or '/',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de operación',
        ondelete='restrict',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Transferencia',
        ondelete='set null',
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('done', 'Finalizada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        required=True,
    )
    line_ids = fields.One2many(
        'kc.internal.lot.scan.session.line',
        'session_id',
        string='Líneas escaneadas',
    )
    created_date = fields.Datetime(
        string='Fecha de creación',
        default=fields.Datetime.now,
        required=True,
    )
    validated_date = fields.Datetime(
        string='Fecha de validación',
    )
    mark_low_quality = fields.Boolean(
        string='Marcar baja calidad',
        help='Indica si los lotes fueron marcados como baja calidad en esta sesión.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = seq.next_by_code('kc.internal.lot.scan.session') or '/'
        return super().create(vals_list)


class KcInternalLotScanSessionLine(models.Model):
    _name = 'kc.internal.lot.scan.session.line'
    _description = 'Línea de sesión de escaneo interno GS1'
    _order = 'product_id, lot_id, id'

    session_id = fields.Many2one(
        'kc.internal.lot.scan.session',
        string='Sesión',
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
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
        required=True,
    )
    barcode_raw = fields.Text(
        string='QR escaneado',
        required=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
        required=True,
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
        required=True,
    )

    _sql_constraints = [
        (
            'session_lot_unique',
            'unique(session_id, lot_id)',
            'Este lote ya fue escaneado en esta sesión.',
        ),
    ]

    @api.constrains('session_id', 'barcode_raw')
    def _check_duplicate_barcode(self):
        for line in self:
            if not line.barcode_raw:
                continue
            duplicate = self.search([
                ('session_id', '=', line.session_id.id),
                ('barcode_raw', '=', line.barcode_raw),
                ('id', '!=', line.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _('Este lote ya fue escaneado en esta sesión.')
                )

    def action_remove_line(self):
        """Elimina la línea escaneada y marca el log como cancelado."""
        self.ensure_one()
        Log = self.env['kc.internal.lot.scan.log']
        log = Log.search([
            ('session_name', '=', self.session_id.name),
            ('lot_id', '=', self.lot_id.id),
            ('state', '=', 'scanned'),
        ], limit=1)
        if log:
            log.state = 'cancelled'
        wizard = self.env['kc.internal.lot.transfer.wizard'].search([
            ('session_id', '=', self.session_id.id),
        ], order='id desc', limit=1)
        self.unlink()
        if wizard:
            return wizard._reload_wizard()
        return True
