# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    kc_gs1_reservation_cleared = fields.Boolean(
        string='Reserva limpiada por wizard GS1',
        copy=False,
        help='Indica que ya se liberaron reservas automáticas al primer escaneo GS1.',
    )
    kc_gs1_scan_log_ids = fields.One2many(
        'kc.gs1.picking.scan.log',
        'picking_id',
        string='Escaneos GS1',
    )

    def action_kc_open_gs1_scan_wizard(self):
        self.ensure_one()
        picking_type = self.picking_type_id
        if not picking_type.kc_enable_gs1_dispatch_wizard:
            raise UserError(_('El tipo de operación no tiene activo el wizard GS1.'))
        if self.state in ('done', 'cancel'):
            raise UserError(_('La operación no está en un estado válido para escanear.'))
        if self.state not in ('confirmed', 'assigned', 'waiting'):
            raise UserError(_('La operación no está en un estado válido para escanear.'))
        self._kc_gs1_cleanup_orphan_scan_logs()
        self._kc_gs1_reset_scan_state_if_empty()
        wizard = self.env['kc.gs1.picking.scan.wizard'].create({
            'picking_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escanear GS1'),
            'res_model': 'kc.gs1.picking.scan.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _kc_sale_line_qty_delivered_done(self, sale_line):
        """Cantidad neta entregada ya confirmada (movimientos salida hechos − devoluciones hechas), en UdM de la línea."""
        self.ensure_one()
        outgoing_moves, incoming_moves = sale_line._get_outgoing_incoming_moves()
        qty = 0.0
        for move in outgoing_moves:
            if move.state != 'done':
                continue
            qty += move.product_uom._compute_quantity(
                move.quantity, sale_line.product_uom, rounding_method='HALF-UP'
            )
        for move in incoming_moves:
            if move.state != 'done':
                continue
            qty -= move.product_uom._compute_quantity(
                move.quantity, sale_line.product_uom, rounding_method='HALF-UP'
            )
        return qty

    def _check_outgoing_delivery_tolerance(self):
        """Límite de excedente sobre cantidad pedida (línea de venta): entregado acumulado + este albarán."""
        for picking in self:
            if picking.state in ('done', 'cancel'):
                continue
            if picking.picking_type_id.code != 'outgoing':
                continue
            partner = picking.partner_id.commercial_partner_id
            tolerance_pct = partner.delivery_excess_max_percent or 0.0

            qty_per_sol = defaultdict(float)
            for move in picking.move_ids:
                if move.state in ('done', 'cancel') or move.scrapped:
                    continue
                if not move.sale_line_id:
                    continue
                rounding = move.product_uom.rounding
                if float_is_zero(move.quantity, precision_rounding=rounding):
                    continue
                qty_in_sol_uom = move.product_uom._compute_quantity(
                    move.quantity,
                    move.sale_line_id.product_uom,
                    rounding_method='HALF-UP',
                )
                qty_per_sol[move.sale_line_id.id] += qty_in_sol_uom

            for sol_id, qty_this_picking in qty_per_sol.items():
                line = self.env['sale.order.line'].browse(sol_id)
                rounding = line.product_uom.rounding
                ordered = line.product_uom_qty
                if float_is_zero(ordered, precision_rounding=rounding):
                    raise UserError(
                        _(
                            'En la entrega %(picking)s la línea de venta %(sol)s tiene cantidad pedida 0 '
                            'pero se intenta entregar %(qty)s; corrija el pedido o el albarán.'
                        )
                        % {
                            'picking': picking.display_name,
                            'sol': line.display_name,
                            'qty': qty_this_picking,
                        }
                    )
                delivered_done = picking._kc_sale_line_qty_delivered_done(line)
                projected = delivered_done + qty_this_picking
                max_allowed = ordered * (1.0 + tolerance_pct / 100.0)
                if float_compare(projected, max_allowed, precision_rounding=rounding) > 0:
                    excess_vs_ordered = ((projected - ordered) / ordered) * 100.0
                    raise UserError(
                        _(
                            'No se puede validar: el total entregado superaría el máximo permitido para el cliente.\n\n'
                            'Línea de venta: %(sol)s\n'
                            'Producto: %(product)s\n'
                            '- Cantidad pedida: %(ordered)s %(uom)s\n'
                            '- Ya entregado (confirmado): %(delivered)s %(uom)s\n'
                            '- Esta entrega: %(this)s %(uom)s\n'
                            '- Total si se valida: %(projected)s %(uom)s (excedente sobre pedido: %(excess).2f%%)\n'
                            '- Cliente: %(partner)s\n'
                            '- Máx. %% excedente configurado: %(tolerance).2f%% '
                            '(cantidad máxima total permitida: %(max)s %(uom)s).'
                        )
                        % {
                            'sol': line.display_name,
                            'product': line.product_id.display_name,
                            'ordered': ordered,
                            'delivered': delivered_done,
                            'this': qty_this_picking,
                            'projected': projected,
                            'uom': line.product_uom.name,
                            'excess': excess_vs_ordered,
                            'partner': partner.display_name or _('(sin cliente)'),
                            'tolerance': tolerance_pct,
                            'max': max_allowed,
                        }
                    )

            for move in picking.move_ids:
                if move.state in ('done', 'cancel') or move.scrapped:
                    continue
                if move.sale_line_id:
                    continue
                rounding = move.product_uom.rounding
                demand = move.product_uom_qty
                done_qty = move.quantity
                if float_is_zero(done_qty, precision_rounding=rounding):
                    continue
                if float_is_zero(demand, precision_rounding=rounding):
                    raise UserError(
                        _(
                            'En la entrega %(picking)s el producto %(product)s tiene cantidad hecha '
                            'pero demanda 0; corrija cantidades o la línea de movimiento.'
                        )
                        % {
                            'picking': picking.display_name,
                            'product': move.product_id.display_name,
                        }
                    )
                max_allowed = demand * (1.0 + tolerance_pct / 100.0)
                if float_compare(done_qty, max_allowed, precision_rounding=rounding) > 0:
                    excess_pct = ((done_qty - demand) / demand) * 100.0
                    raise UserError(
                        _(
                            'No se puede validar: el excedente de entrega supera el máximo permitido '
                            'para el cliente (movimiento sin línea de venta; se usa la demanda del movimiento).\n\n'
                            '- Producto: %(product)s\n'
                            '- Demanda: %(demand)s %(uom)s\n'
                            '- Cantidad a validar: %(done)s %(uom)s\n'
                            '- Excedente sobre la demanda: %(excess).2f%%\n'
                            '- Cliente: %(partner)s\n'
                            '- Máx. %% excedente configurado: %(tolerance).2f%% '
                            '(cantidad máxima permitida: %(max)s %(uom)s).'
                        )
                        % {
                            'product': move.product_id.display_name,
                            'demand': demand,
                            'done': done_qty,
                            'uom': move.product_uom.name,
                            'excess': excess_pct,
                            'partner': partner.display_name or _('(sin cliente)'),
                            'tolerance': tolerance_pct,
                            'max': max_allowed,
                        }
                    )

    def _action_done(self):
        self._check_outgoing_delivery_tolerance()
        return super()._action_done()

    def _kc_check_low_quality_lot_allowed(self, lot):
        """Bloquea lotes de baja calidad si el cliente no lo permite (entregas)."""
        self.ensure_one()
        if not lot or not lot.low_quality:
            return
        if self.state in ('done', 'cancel') or self.picking_type_id.code != 'outgoing':
            return
        partner = self.partner_id.commercial_partner_id
        if not partner.scan_lote_quality_low:
            raise UserError(
                _('Este cliente no permite entregar lotes marcados como baja calidad.')
            )

    def _kc_gs1_register_done_quantity(self, move, lot, qty, location, location_dest):
        """Registra cantidad hecha + lote en el movimiento (pestaña Operaciones del albarán)."""
        self.ensure_one()
        move.ensure_one()
        lot.ensure_one()
        rounding = move.product_uom.rounding

        if not self.kc_gs1_reservation_cleared:
            self.do_unreserve()
            self.kc_gs1_reservation_cleared = True

        MoveLine = self.env['stock.move.line']
        existing = move.move_line_ids.filtered(
            lambda ml: ml.lot_id == lot and ml.state not in ('done', 'cancel')
        )
        if existing:
            move_line = existing[0]
            new_qty = move_line.quantity + qty
            move_line.write({
                'quantity': new_qty,
                'picked': True,
                'location_id': location.id,
                'location_dest_id': location_dest.id,
            })
        else:
            move_line = MoveLine.create({
                'picking_id': self.id,
                'move_id': move.id,
                'product_id': move.product_id.id,
                'lot_id': lot.id,
                'location_id': location.id,
                'location_dest_id': location_dest.id,
                'product_uom_id': move.product_uom.id,
                'quantity': qty,
                'picked': True,
            })

        move.picked = True
        move.invalidate_recordset(['quantity', 'move_line_ids'])
        self.invalidate_recordset(['move_ids', 'move_line_ids'])
        self.env.flush_all()

        if float_is_zero(move.quantity, precision_rounding=rounding):
            raise UserError(
                _(
                    'No se pudo registrar la cantidad en el albarán para el lote %(lot)s. '
                    'Revise permisos o el estado de la operación.'
                )
                % {'lot': lot.display_name}
            )
        return move_line

    def _kc_gs1_cleanup_orphan_scan_logs(self):
        """Borra logs de escaneo que ya no tienen respaldo en líneas de movimiento."""
        self.ensure_one()
        Log = self.env['kc.gs1.picking.scan.log']
        logs = Log.search([('picking_id', '=', self.id)])
        if not logs:
            return
        orphan_logs = self.env['kc.gs1.picking.scan.log']
        for log in logs:
            backed = self.move_line_ids.filtered(
                lambda ml, log=log: ml.product_id == log.product_id
                and ml.lot_id == log.lot_id
                and ml.state not in ('done', 'cancel')
                and not float_is_zero(ml.quantity, precision_rounding=ml.product_uom_id.rounding)
            )
            if not backed:
                orphan_logs |= log
        if orphan_logs:
            orphan_logs.unlink()

    def _kc_gs1_reset_scan_state_if_empty(self):
        """Si no hay cantidades hechas en la operación, reinicia bandera de reserva GS1."""
        self.ensure_one()
        moves = self.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and not m.scrapped
        )
        has_done_qty = any(
            not float_is_zero(m.quantity, precision_rounding=m.product_uom.rounding)
            for m in moves
        )
        if not has_done_qty:
            self.kc_gs1_reservation_cleared = False

    def _kc_resolve_lot_for_scan(self, product_id, lot_id, lot_name):
        Lot = self.env['stock.lot']
        if lot_id:
            lot = Lot.browse(lot_id)
            return lot if lot.exists() else Lot
        if lot_name and product_id:
            return Lot.search(
                [
                    ('name', '=', lot_name),
                    ('product_id', '=', product_id),
                    '|',
                    ('company_id', '=', False),
                    ('company_id', '=', self.company_id.id),
                ],
                limit=1,
            )
        return Lot

    def _kc_barcode_check_outgoing_scan_impl(self, params):
        """Validaciones de escaneo en salidas: baja calidad y tolerancia (misma lógica que al validar)."""
        self.ensure_one()
        if self.state in ('done', 'cancel') or self.picking_type_id.code != 'outgoing':
            return
        partner = self.partner_id.commercial_partner_id
        product_id = params.get('product_id')
        lot_id = params.get('lot_id') or False
        lot_name = params.get('lot_name') or False
        move_id = params.get('move_id') or False
        qty_delta = float(params.get('qty_delta') or 0.0)
        projected_move_qty = float(params.get('projected_move_qty') or 0.0)

        lot = self._kc_resolve_lot_for_scan(product_id, lot_id, lot_name)
        self._kc_check_low_quality_lot_allowed(lot)

        move = self.env['stock.move'].browse(move_id)
        if not move_id or not move.exists() or move.picking_id != self:
            return
        rounding = move.product_uom.rounding
        if float_is_zero(qty_delta, precision_rounding=rounding):
            return

        tolerance_pct = partner.delivery_excess_max_percent or 0.0

        if move.sale_line_id:
            sol = move.sale_line_id
            sol_rounding = sol.product_uom.rounding
            ordered = sol.product_uom_qty
            if float_is_zero(ordered, precision_rounding=sol_rounding):
                return
            delivered_done = self._kc_sale_line_qty_delivered_done(sol)
            qty_this_picking = 0.0
            for m in self.move_ids:
                if m.state in ('done', 'cancel') or m.scrapped or not m.sale_line_id:
                    continue
                if m.sale_line_id != sol:
                    continue
                q_move_uom = projected_move_qty if m.id == move.id else m.quantity
                qty_this_picking += m.product_uom._compute_quantity(
                    q_move_uom, sol.product_uom, rounding_method='HALF-UP'
                )
            projected = delivered_done + qty_this_picking
            max_allowed = ordered * (1.0 + tolerance_pct / 100.0)
            if float_compare(projected, max_allowed, precision_rounding=sol_rounding) > 0:
                raise UserError(
                    _(
                        'Con este escaneo se supera el máximo de entrega permitido para el cliente '
                        '(pedido %(ordered)s %(uom)s, máximo %(max)s %(uom)s con el %% configurado).'
                    )
                    % {
                        'ordered': ordered,
                        'max': max_allowed,
                        'uom': sol.product_uom.name,
                    }
                )
        else:
            demand = move.product_uom_qty
            if float_is_zero(demand, precision_rounding=rounding):
                return
            max_allowed = demand * (1.0 + tolerance_pct / 100.0)
            if float_compare(projected_move_qty, max_allowed, precision_rounding=rounding) > 0:
                raise UserError(
                    _(
                        'Con este escaneo se supera el máximo de entrega permitido para el cliente '
                        '(demanda %(demand)s %(uom)s, máximo %(max)s %(uom)s).'
                    )
                    % {
                        'demand': demand,
                        'max': max_allowed,
                        'uom': move.product_uom.name,
                    }
                )

    @api.model
    def kc_barcode_check_outgoing_scan(self, picking_id, params):
        picking = self.browse(picking_id).exists()
        if not picking:
            return {'error': False}
        try:
            picking._kc_barcode_check_outgoing_scan_impl(params)
        except UserError as e:
            return {'error': True, 'message': e.args[0] if e.args else str(e)}
        return {'error': False}

    def action_kc_print_all_lot_labels(self):
        self.ensure_one()
        if self.picking_type_id.code != 'incoming':
            raise UserError(_('Solo aplica a albaranes de entrada.'))
        if self.state != 'done':
            raise UserError(_('Valide el albarán antes de imprimir las etiquetas de lote.'))
        lots = self.move_line_ids.mapped('lot_id')
        if not lots:
            raise UserError(_('No hay números de lote en este albarán.'))
        wiz = self.env['kc.lot.label.print.wizard'].create({
            'lot_ids': [(6, 0, lots.ids)],
            'label_profile': 'supplier',
            'picking_id': self.id,
            'lock_supplier_profile': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Etiquetas Zebra (proveedor)'),
            'res_model': 'kc.lot.label.print.wizard',
            'view_mode': 'form',
            'res_id': wiz.id,
            'target': 'new',
        }
