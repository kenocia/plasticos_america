# -*- coding: utf-8 -*-

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class KcGs1PickingScanWizardSummary(models.TransientModel):
    _name = 'kc.gs1.picking.scan.wizard.summary'
    _description = 'Resumen pedido vs despachado (wizard GS1)'
    _order = 'product_id'

    wizard_id = fields.Many2one(
        'kc.gs1.picking.scan.wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='UdM', readonly=True)
    qty_ordered = fields.Float(
        string='Pedido',
        readonly=True,
        digits='Product Unit of Measure',
    )
    qty_done = fields.Float(
        string='Despachado',
        readonly=True,
        digits='Product Unit of Measure',
    )
    qty_pending = fields.Float(
        string='Pendiente',
        readonly=True,
        digits='Product Unit of Measure',
    )


class KcGs1PickingScanWizard(models.TransientModel):
    _name = 'kc.gs1.picking.scan.wizard'
    _description = 'Wizard de escaneo GS1 para operaciones de inventario'
    _inherit = ['kc.gs1.barcode.mixin']

    picking_id = fields.Many2one(
        'stock.picking',
        string='Operación',
        required=True,
        readonly=True,
    )
    barcode_input = fields.Char(
        string='Escanear QR GS1',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        readonly=True,
    )
    qty_gs1 = fields.Float(
        string='Cantidad QR',
        readonly=True,
        digits='Product Unit of Measure',
    )
    available_qty = fields.Float(
        string='Disponible',
        readonly=True,
        digits='Product Unit of Measure',
    )
    pending_qty = fields.Float(
        string='Pendiente',
        readonly=True,
        digits='Product Unit of Measure',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
        readonly=True,
    )
    message = fields.Text(
        string='Mensaje',
        readonly=True,
    )
    state = fields.Selection(
        [
            ('scan', 'Escanear'),
            ('confirm', 'Confirmar'),
            ('done', 'Aplicado'),
            ('error', 'Error'),
        ],
        string='Estado',
        default='scan',
        readonly=True,
    )
    barcode_raw = fields.Text(
        string='QR procesado',
        readonly=True,
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
        help='Técnico: incrementa tras cada escaneo para devolver el foco al campo QR.',
    )
    scan_log_ids = fields.Many2many(
        'kc.gs1.picking.scan.log',
        compute='_compute_scan_log_ids',
        string='Lotes escaneados',
    )
    scan_log_count = fields.Integer(
        string='Líneas en rampa',
        compute='_compute_scan_log_count',
    )
    kc_scan_refresh = fields.Integer(
        default=0,
        help='Técnico: fuerza refresco de la lista de escaneos en el wizard.',
    )
    scan_session_uid = fields.Char(
        string='Sesión de escaneo',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
    )
    summary_line_ids = fields.One2many(
        'kc.gs1.picking.scan.wizard.summary',
        'wizard_id',
        string='Pendiente por despachar',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_dispatch_summary()
        return records

    @api.depends('picking_id', 'scan_session_uid', 'kc_scan_refresh')
    def _compute_scan_log_ids(self):
        Log = self.env['kc.gs1.picking.scan.log']
        for wizard in self:
            if wizard.picking_id and wizard.scan_session_uid:
                wizard.scan_log_ids = Log.search(
                    [
                        ('picking_id', '=', wizard.picking_id.id),
                        ('scan_session_uid', '=', wizard.scan_session_uid),
                    ],
                    order='session_line_no desc, scan_date desc, id desc',
                )
            else:
                wizard.scan_log_ids = Log

    @api.depends('scan_log_ids', 'kc_scan_refresh')
    def _compute_scan_log_count(self):
        for wizard in self:
            wizard.scan_log_count = len(wizard.scan_log_ids)

    def _refresh_dispatch_summary(self):
        """Líneas pedido / despachado / pendiente por producto en la operación."""
        Summary = self.env['kc.gs1.picking.scan.wizard.summary']
        for wizard in self:
            if not wizard.picking_id:
                wizard.summary_line_ids = [(5, 0, 0)]
                continue
            by_product = {}
            moves = wizard.picking_id.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and not m.scrapped
            )
            for move in moves:
                product = move.product_id
                pid = product.id
                if pid not in by_product:
                    by_product[pid] = {
                        'product_id': pid,
                        'product_uom_id': move.product_uom.id,
                        'qty_ordered': 0.0,
                        'qty_done': 0.0,
                    }
                by_product[pid]['qty_ordered'] += move.product_uom_qty
                by_product[pid]['qty_done'] += move.quantity
            old_lines = Summary.search([('wizard_id', '=', wizard.id)])
            if old_lines:
                old_lines.unlink()
            line_vals = []
            for data in sorted(by_product.values(), key=lambda d: d['product_id']):
                pending = max(data['qty_ordered'] - data['qty_done'], 0.0)
                line_vals.append({
                    'wizard_id': wizard.id,
                    'product_id': data['product_id'],
                    'product_uom_id': data['product_uom_id'],
                    'qty_ordered': data['qty_ordered'],
                    'qty_done': data['qty_done'],
                    'qty_pending': pending,
                })
            if line_vals:
                Summary.create(line_vals)

    def _find_lot(self, product, lot_name):
        return self.kc_gs1_find_lot(product, lot_name, self.picking_id.company_id)

    def _ensure_product_on_picking(self, product):
        """El producto del QR debe existir como movimiento en esta operación."""
        self.ensure_one()
        picking_products = self.picking_id.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and not m.scrapped
        ).product_id
        if product not in picking_products:
            raise UserError(
                _(
                    'El producto «%(product)s» no está en esta operación (%(picking)s). '
                    'Los productos del albarán son: %(lines)s'
                )
                % {
                    'product': product.display_name,
                    'picking': self.picking_id.display_name,
                    'lines': ', '.join(picking_products.mapped('display_name')) or _('(ninguno)'),
                }
            )

    def _get_active_moves_for_product(self, product):
        self.ensure_one()
        return self.picking_id.move_ids.filtered(
            lambda m: m.product_id == product
            and m.state not in ('done', 'cancel')
            and not m.scrapped
        )

    def _get_product_pending_qty(self, product):
        self.ensure_one()
        moves = self._get_active_moves_for_product(product)
        if not moves:
            return 0.0, moves
        demand = sum(moves.mapped('product_uom_qty'))
        done = sum(moves.mapped('quantity'))
        return max(demand - done, 0.0), moves

    def _select_move_for_qty(self, moves, qty):
        rounding = moves[:1].product_uom.rounding if moves else 0.01
        candidates = []
        for move in moves:
            move_pending = move.product_uom_qty - move.quantity
            if float_compare(move_pending, qty, precision_rounding=rounding) >= 0:
                candidates.append((move_pending, move))
        if not candidates:
            return self.env['stock.move']
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _resolve_quant_location(self, product, lot, qty):
        """Ubicación con un quant que cubra la cantidad completa del QR."""
        self.ensure_one()
        picking = self.picking_id
        Quant = self.env['stock.quant']
        quants = Quant.search([
            ('product_id', '=', product.id),
            ('lot_id', '=', lot.id),
            ('location_id', 'child_of', picking.location_id.id),
        ])
        rounding = product.uom_id.rounding
        available_entries = []
        total_available = 0.0
        for quant in quants:
            avail = quant.quantity - quant.reserved_quantity
            if float_compare(avail, 0.0, precision_rounding=rounding) <= 0:
                continue
            available_entries.append((quant, avail))
            total_available += avail

        covering = [
            q for q, avail in available_entries
            if float_compare(avail, qty, precision_rounding=rounding) >= 0
        ]
        if len(covering) == 1:
            q = covering[0]
            return q.location_id, q.quantity - q.reserved_quantity
        if len(covering) > 1:
            best = max(
                [(q, q.quantity - q.reserved_quantity) for q in covering],
                key=lambda item: item[1],
            )
            return best[0].location_id, best[1]

        if float_compare(total_available, qty, precision_rounding=rounding) >= 0:
            raise UserError(
                _('El lote %(lot)s tiene disponibilidad distribuida en varias ubicaciones '
                  'y no se permite partir el QR.')
                % {'lot': lot.display_name}
            )

        loc_name = picking.location_id.display_name
        raise UserError(
            _('El lote %(lot)s no tiene disponibilidad suficiente en la ubicación %(loc)s. '
              'Disponible: %(avail)s, requerido: %(req)s.')
            % {
                'lot': lot.display_name,
                'loc': loc_name,
                'avail': total_available,
                'req': qty,
            }
        )

    def _is_duplicate_scan(self, lot, barcode_raw):
        self.ensure_one()
        picking = self.picking_id
        if not picking.picking_type_id.kc_gs1_block_duplicate_scan:
            return False
        Log = self.env['kc.gs1.picking.scan.log']
        domain = [('picking_id', '=', picking.id)]
        if self.scan_session_uid:
            domain.append(('scan_session_uid', '=', self.scan_session_uid))
        if Log.search(domain + [('lot_id', '=', lot.id)], limit=1):
            return True
        if barcode_raw and Log.search(domain + [('barcode_raw', '=', barcode_raw)], limit=1):
            return True
        existing_line = picking.move_line_ids.filtered(
            lambda ml: ml.lot_id == lot
            and ml.product_id == lot.product_id
            and ml.state not in ('done', 'cancel')
            and not float_is_zero(ml.quantity, precision_rounding=ml.product_uom_id.rounding)
        )
        return bool(existing_line)

    def _reset_for_next_scan(self, message):
        """Limpia el QR y deja el wizard listo para otro escaneo (con foco en JS)."""
        self.write({
            'barcode_input': False,
            'product_id': False,
            'lot_id': False,
            'qty_gs1': 0.0,
            'available_qty': 0.0,
            'pending_qty': 0.0,
            'location_id': False,
            'location_dest_id': False,
            'barcode_raw': False,
            'message': message,
            'state': 'scan',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
            'kc_scan_refresh': (self.kc_scan_refresh or 0) + 1,
        })
        self._refresh_dispatch_summary()
        if self.picking_id:
            self.picking_id.invalidate_recordset(
                ['move_ids', 'move_line_ids', 'kc_gs1_scan_log_ids']
            )

    def _set_scan_error(self, message):
        self.ensure_one()
        self.write({
            'barcode_input': False,
            'message': message,
            'state': 'error',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
        })

    def _abort_duplicate_scan(self):
        self.ensure_one()
        self._reset_for_next_scan(
            _('Este QR/lote ya fue escaneado en esta operación. Escanee otro código.')
        )

    def _validate_picking_for_scan(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking.picking_type_id.kc_enable_gs1_dispatch_wizard:
            raise UserError(_('El tipo de operación no tiene activo el wizard GS1.'))
        if picking.state in ('done', 'cancel'):
            raise UserError(_('La operación no está en un estado válido para escanear.'))

    def _barcode_scan_raw(self):
        """Código del campo guardado o del contexto (handheld antes del save)."""
        self.ensure_one()
        raw = (self.barcode_input or '').strip()
        if not raw:
            raw = (self.env.context.get('kc_gs1_barcode_scan') or '').strip()
        return raw

    def _sync_barcode_from_context(self):
        raw = self._barcode_scan_raw()
        if raw and not (self.barcode_input or '').strip():
            self.barcode_input = raw
        return raw

    def _reopen_wizard_action(self):
        """Reabre el mismo wizard en modal (Odoo 18: return False cierra el diálogo)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escanear GS1'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': dict(self.env.context),
        }

    @staticmethod
    def _set_move_line_quantity(move_line, qty):
        # Odoo 18: quantity; versiones anteriores usaban qty_done.
        if 'quantity' in move_line._fields:
            move_line.quantity = qty
        elif 'qty_done' in move_line._fields:
            move_line.qty_done = qty
        else:
            raise UserError(_('No se encontró campo de cantidad en stock.move.line.'))
        if 'picked' in move_line._fields:
            move_line.picked = True

    def _do_process_qr(self):
        """Valida el QR y deja el wizard en confirm. Devuelve False si fue duplicado."""
        self.ensure_one()
        picking = self.picking_id
        barcode = self._sync_barcode_from_context()
        if not barcode:
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )

        parsed = self.parse_gs1_barcode(barcode)
        product = self.kc_gs1_find_product(parsed['product_code'])
        if not product:
            raise UserError(
                _('Producto no encontrado para el código GS1: %s') % parsed['product_code']
            )
        self._ensure_product_on_picking(product)

        pending_qty, moves = self._get_product_pending_qty(product)
        if not moves:
            raise UserError(_('El producto escaneado no pertenece a esta operación.'))
        if float_is_zero(pending_qty, precision_rounding=product.uom_id.rounding):
            raise UserError(_('El producto escaneado no pertenece a esta operación.'))

        qty_gs1 = parsed['qty']
        rounding = product.uom_id.rounding
        if float_compare(qty_gs1, pending_qty, precision_rounding=rounding) > 0:
            raise UserError(
                _('La cantidad del QR (%(qr)s) supera la cantidad pendiente del producto '
                  'en esta operación (%(pending)s). No se permite partir lotes.')
                % {'qr': qty_gs1, 'pending': pending_qty}
            )

        lot = self._find_lot(product, parsed['lot_name'])
        if not lot:
            raise UserError(
                _('El lote %(lot)s no existe para el producto %(product)s.')
                % {'lot': parsed['lot_name'], 'product': product.display_name}
            )
        if lot.product_id != product:
            raise UserError(
                _('El lote %(lot)s pertenece a %(lot_product)s, no a %(product)s.')
                % {
                    'lot': lot.display_name,
                    'lot_product': lot.product_id.display_name,
                    'product': product.display_name,
                }
            )

        if self._is_duplicate_scan(lot, barcode):
            self._abort_duplicate_scan()
            return False

        picking._kc_check_low_quality_lot_allowed(lot)

        loc, available_qty = self._resolve_quant_location(product, lot, qty_gs1)

        self.write({
            'product_id': product.id,
            'lot_id': lot.id,
            'qty_gs1': qty_gs1,
            'available_qty': available_qty,
            'pending_qty': pending_qty,
            'location_id': loc.id,
            'location_dest_id': picking.location_dest_id.id,
            'barcode_raw': barcode,
            'message': _(
                'QR válido.\n'
                'Producto: %(product)s\n'
                'Lote: %(lot)s\n'
                'Cantidad QR: %(qty)s\n'
                'Disponible en ubicación: %(avail)s\n'
                'Pendiente en operación: %(pending)s'
            ) % {
                'product': product.display_name,
                'lot': lot.display_name,
                'qty': qty_gs1,
                'avail': available_qty,
                'pending': pending_qty,
            },
            'state': 'confirm',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
        })
        return True

    def action_process_qr(self):
        self.ensure_one()
        try:
            self._validate_picking_for_scan()
            self._do_process_qr()
        except (UserError, ValidationError) as err:
            self._set_scan_error(err.args[0] if err.args else str(err))
        return self._reopen_wizard_action()

    def _do_apply_scan(self):
        self.ensure_one()
        if self.state != 'confirm':
            raise UserError(_('Primero procese un QR válido.'))

        picking = self.picking_id
        product = self.product_id
        lot = self.lot_id
        qty = self.qty_gs1
        rounding = product.uom_id.rounding

        pending_qty, moves = self._get_product_pending_qty(product)
        if float_compare(qty, pending_qty, precision_rounding=rounding) > 0:
            raise UserError(
                _('La cantidad del QR supera la cantidad pendiente. No se permite partir lotes.')
            )

        move = self._select_move_for_qty(moves, qty)
        if not move:
            raise UserError(_('No se encontró movimiento pendiente para el producto escaneado.'))

        if self._is_duplicate_scan(lot, self.barcode_raw):
            self._abort_duplicate_scan()
            return

        picking._kc_check_low_quality_lot_allowed(lot)
        picking._kc_gs1_register_done_quantity(
            move,
            lot,
            qty,
            self.location_id,
            self.location_dest_id,
        )

        self.env['kc.gs1.picking.scan.log'].create({
            'picking_id': picking.id,
            'product_id': product.id,
            'lot_id': lot.id,
            'qty': qty,
            'barcode_raw': self.barcode_raw,
            'scan_session_uid': self.scan_session_uid,
        })

        success_msg = _(
            'Escaneo aplicado: %(qty)s %(uom)s del lote %(lot)s. '
        ) % {
            'qty': qty,
            'uom': product.uom_id.name,
            'lot': lot.display_name,
        }

        self._reset_for_next_scan(success_msg)

    def action_apply_scan(self):
        self.ensure_one()
        try:
            self._validate_picking_for_scan()
            self._do_apply_scan()
        except (UserError, ValidationError) as err:
            self._set_scan_error(err.args[0] if err.args else str(err))
        return self._reopen_wizard_action()

    def action_on_barcode_scanned(self):
        """Handheld: Enter en el campo QR → procesar y aplicar en un paso."""
        self.ensure_one()
        if not self._sync_barcode_from_context():
            return self._reopen_wizard_action()
        try:
            self._validate_picking_for_scan()
            if self._do_process_qr():
                self._do_apply_scan()
        except (UserError, ValidationError) as err:
            self._set_scan_error(err.args[0] if err.args else str(err))
        return self._reopen_wizard_action()

    def action_clear_ramp(self):
        """Limpia el listado de la rampa actual (nueva sesión de conteo, sin deshacer stock)."""
        self.ensure_one()
        Log = self.env['kc.gs1.picking.scan.log']
        if self.picking_id and self.scan_session_uid:
            logs = Log.search([
                ('picking_id', '=', self.picking_id.id),
                ('scan_session_uid', '=', self.scan_session_uid),
            ])
            if logs:
                logs.unlink()
        self.write({
            'scan_session_uid': str(uuid.uuid4()),
            'barcode_input': False,
            'product_id': False,
            'lot_id': False,
            'qty_gs1': 0.0,
            'available_qty': 0.0,
            'pending_qty': 0.0,
            'location_id': False,
            'location_dest_id': False,
            'barcode_raw': False,
            'message': _('Rampa limpiada.'),
            'state': 'scan',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
            'kc_scan_refresh': (self.kc_scan_refresh or 0) + 1,
        })
        self._refresh_dispatch_summary()
        if self.picking_id:
            self.picking_id.invalidate_recordset(
                ['move_ids', 'move_line_ids', 'kc_gs1_scan_log_ids']
            )
        return self._reopen_wizard_action()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
