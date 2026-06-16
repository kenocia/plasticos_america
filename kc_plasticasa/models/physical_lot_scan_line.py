# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero


class KcPhysicalLotScanLine(models.Model):
    _name = 'kc.physical.lot.scan.line'
    _description = 'Línea de levantamiento físico previo por lote'
    _order = 'ramp_index desc, session_line_no desc, id desc'

    session_id = fields.Many2one(
        'kc.physical.lot.scan.session',
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
        index=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        required=True,
    )
    qty_gs1 = fields.Float(
        string='Cantidad QR',
        digits='Product Unit of Measure',
        help='Cantidad leída del AI 30 del código GS1 (informativa).',
    )
    qty_physical = fields.Float(
        string='Cantidad en Odoo',
        digits='Product Unit of Measure',
        help='Existencia del lote en Odoo en la ubicación reportada (no incluye otras ubicaciones).',
    )
    location_reported_id = fields.Many2one(
        'stock.location',
        string='Ubicación reportada',
        required=True,
        ondelete='restrict',
    )
    location_system_id = fields.Many2one(
        'stock.location',
        string='Ubicación en Odoo',
        ondelete='set null',
        help='Ubicación del lote en inventario (location_id o mayor existencia) al escanear.',
    )
    location_mismatch = fields.Boolean(
        string='Diferencia ubicación',
        compute='_compute_location_mismatch',
        store=True,
    )
    has_stock_at_reported = fields.Boolean(
        string='Con stock en ubic. reportada',
        compute='_compute_has_stock_at_reported',
        store=True,
        help='True si Odoo aún registra existencia del lote en la ubicación reportada.',
    )
    odoo_refreshed_date = fields.Datetime(
        string='Odoo actualizado',
        readonly=True,
    )
    adjustment_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento ajuste',
        ondelete='set null',
        copy=False,
        readonly=True,
    )
    return_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento devolución',
        ondelete='set null',
        copy=False,
        readonly=True,
    )
    barcode_raw = fields.Text(
        string='QR escaneado',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario escaneo',
        default=lambda self: self.env.user,
        required=True,
    )
    scan_date = fields.Datetime(
        string='Fecha escaneo',
        default=fields.Datetime.now,
        required=True,
    )
    scan_session_uid = fields.Char(
        string='Rampla (UID)',
        index=True,
        help='Identificador de la rampla actual dentro de la sesión de levantamiento.',
    )
    ramp_index = fields.Integer(
        string='Rampla',
        index=True,
        default=1,
        help='Número de rampla dentro de la sesión (1, 2, 3…).',
    )
    session_line_no = fields.Integer(
        string='#',
        readonly=True,
        index=True,
        help='Correlativo global: rampla 1 desde 1, rampla 2 desde 100, rampla 3 desde 200, etc.',
    )
    last_movement_id = fields.Many2one(
        'stock.picking',
        string='Último movimiento',
        ondelete='set null',
        help='Último albarán validado del lote al escanear (trazabilidad); snapshot en la sesión.',
    )
    last_movement_date = fields.Datetime(
        string='Fecha último movimiento',
    )
    last_movement_user_id = fields.Many2one(
        'res.users',
        string='Usuario último movimiento',
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        related='session_id.company_id',
        store=True,
        index=True,
    )
    state = fields.Selection(
        related='session_id.state',
        store=True,
    )

    _sql_constraints = [
        (
            'session_lot_unique',
            'unique(session_id, lot_id)',
            'Este lote ya fue escaneado en esta sesión.',
        ),
    ]

    @api.depends('location_reported_id', 'location_system_id')
    def _compute_location_mismatch(self):
        for line in self:
            reported = line.location_reported_id
            system = line.location_system_id
            line.location_mismatch = bool(
                reported and system and reported.id != system.id
            )

    @api.depends('qty_physical', 'product_uom_id')
    def _compute_has_stock_at_reported(self):
        for line in self:
            rounding = line.product_uom_id.rounding if line.product_uom_id else 0.01
            line.has_stock_at_reported = not float_is_zero(
                line.qty_physical or 0.0,
                precision_rounding=rounding,
            )

    def _kc_physical_odoo_snapshot_vals(self):
        """Valores Odoo actuales según la ubicación reportada de la línea."""
        self.ensure_one()
        mixin = self.env['kc.gs1.barcode.mixin']
        company = self.session_id.company_id
        lot = self.lot_id
        location = self.location_reported_id
        stock_company = mixin.kc_lot_stock_company(lot, company)
        qty_physical = mixin.kc_lot_qty_at_location(lot, location, stock_company)
        system_loc = mixin.kc_lot_system_location(lot, stock_company)
        last_move_line = mixin.kc_lot_last_done_move_line(lot, stock_company)
        last_picking = last_move_line.picking_id if last_move_line else False
        last_date = False
        last_user = False
        if last_move_line:
            last_date = last_move_line.date or False
        if last_picking:
            last_date = last_date or last_picking.date_done or last_picking.scheduled_date
            last_user = last_picking.user_id.id if last_picking.user_id else False
        return {
            'qty_physical': qty_physical,
            'location_system_id': system_loc.id if system_loc else False,
            'last_movement_id': last_picking.id if last_picking else False,
            'last_movement_date': last_date,
            'last_movement_user_id': last_user,
            'odoo_refreshed_date': fields.Datetime.now(),
        }

    def action_refresh_odoo_quantities(self):
        for line in self:
            line.write(line._kc_physical_odoo_snapshot_vals())
        return True

    @api.model
    def _ramp_line_base(self, ramp_index):
        ramp_index = ramp_index or 1
        if ramp_index <= 1:
            return 1
        return (ramp_index - 1) * 100

    @api.model
    def _next_session_line_no(self, ramp_index, scan_session_uid, session_id):
        count = self.search_count([
            ('session_id', '=', session_id),
            ('scan_session_uid', '=', scan_session_uid),
        ])
        return self._ramp_line_base(ramp_index) + count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('session_line_no') and vals.get('scan_session_uid'):
                ramp_index = vals.get('ramp_index') or 1
                count = self.search_count([
                    ('session_id', '=', vals.get('session_id')),
                    ('scan_session_uid', '=', vals['scan_session_uid']),
                ])
                vals['session_line_no'] = self._ramp_line_base(ramp_index) + count
        return super().create(vals_list)

    @api.model
    def _prepare_from_gs1_scan(self, session, product, lot, parsed, barcode_raw,
                               location_reported, scan_session_uid=None,
                               ramp_index=None):
        """Snapshot al escanear: lectura de stock.lot / quants / trazabilidad (sin escribir en lote)."""
        mixin = self.env['kc.gs1.barcode.mixin']
        stock_company = mixin.kc_lot_stock_company(lot, session.company_id)
        qty_physical = mixin.kc_lot_qty_at_location(
            lot, location_reported, stock_company,
        )
        system_loc = mixin.kc_lot_system_location(lot, stock_company)
        last_move_line = mixin.kc_lot_last_done_move_line(lot, stock_company)
        last_picking = last_move_line.picking_id if last_move_line else False
        last_date = False
        last_user = False
        if last_move_line:
            last_date = last_move_line.date or False
        if last_picking:
            last_date = last_date or last_picking.date_done or last_picking.scheduled_date
            last_user = last_picking.user_id.id if last_picking.user_id else False
        return {
            'session_id': session.id,
            'product_id': product.id,
            'lot_id': lot.id,
            'product_uom_id': product.uom_id.id,
            'qty_gs1': parsed['qty'],
            'qty_physical': qty_physical,
            'location_reported_id': location_reported.id,
            'location_system_id': system_loc.id if system_loc else False,
            'barcode_raw': barcode_raw,
            'user_id': self.env.user.id,
            'scan_date': fields.Datetime.now(),
            'last_movement_id': last_picking.id if last_picking else False,
            'last_movement_date': last_date,
            'last_movement_user_id': last_user,
            'scan_session_uid': scan_session_uid or False,
            'ramp_index': ramp_index or 1,
        }

    @api.constrains('session_id', 'location_reported_id')
    def _check_location_reported_domain(self):
        mixin = self.env['kc.gs1.barcode.mixin']
        for line in self:
            allowed = mixin.kc_physical_reported_location_ids(
                line.company_id,
                None,
            )
            if line.location_reported_id.id not in allowed:
                raise ValidationError(
                    _('La ubicación reportada no está permitida para levantamiento físico.')
                )

    def action_open_bulk_update_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actualizar ubicación / movimiento'),
            'res_model': 'kc.physical.lot.scan.bulk.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': self.ids, 'active_model': self._name},
        }
