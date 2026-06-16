# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class MrpSemiTicket(models.Model):
    _name = 'mrp.semi.ticket'
    _description = 'Ticket de semiterminado (tablet)'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    operation_id = fields.Many2one(
        'mrp.routing.workcenter',
        string='Operación (lista de materiales)',
        ondelete='set null',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Semiterminado',
        ondelete='restrict',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        required=True,
    )
    quantity = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        required=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
    )
    printed_at = fields.Datetime(
        string='Última impresión',
        readonly=True,
    )
    print_count = fields.Integer(
        string='Veces impreso',
        default=0,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento de stock',
        help='Movimiento de inventario interno generado al registrar el ticket (si la operación tiene tipo y ubicación semi).',
        readonly=True,
        copy=False,
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán',
        related='stock_move_id.picking_id',
        store=True,
        readonly=True,
    )
    kc_semi_qty_available_in_semi = fields.Float(
        string='Existencias en ubicación semi',
        compute='_compute_kc_semi_qty_available_in_semi',
        digits='Product Unit of Measure',
        help='Cantidad en stock en la ubicación semi de la operación, acotada por lote del movimiento del ticket '
             'si el producto es trazable por lote. Sin trazabilidad puede coincidir con el total del producto en la ubicación.',
    )

    @api.depends(
        'stock_move_id',
        'stock_move_id.state',
        'stock_move_id.move_line_ids.lot_id',
        'product_id',
        'product_id.tracking',
        'operation_id.kc_semi_location_id',
        'company_id',
    )
    def _compute_kc_semi_qty_available_in_semi(self):
        Quant = self.env['stock.quant']
        for ticket in self:
            ticket.kc_semi_qty_available_in_semi = 0.0
            if not ticket.product_id or not ticket.product_id.is_storable or not ticket.stock_move_id:
                continue
            op = ticket.operation_id
            if not op or not op.kc_semi_location_id:
                continue
            loc = op.kc_semi_location_id
            domain = [
                ('product_id', '=', ticket.product_id.id),
                ('location_id', 'child_of', loc.id),
                ('company_id', '=', ticket.company_id.id),
            ]
            lots = ticket.stock_move_id.move_line_ids.filtered(lambda ml: ml.lot_id).mapped('lot_id')
            if ticket.product_id.tracking in ('lot', 'serial') and lots:
                domain.append(('lot_id', 'in', lots.ids))
            quants = Quant.search(domain)
            ticket.kc_semi_qty_available_in_semi = sum(quants.mapped('quantity'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mrp.semi.ticket') or vals.get('name', _('New'))
        return super().create(vals_list)

    def _kc_try_create_semi_internal_picking(self):
        """Crea y valida un albarán interno hacia la ubicación semi si la operación está configurada."""
        self.ensure_one()
        ticket = self
        op = ticket.operation_id
        if not op or not op.kc_semi_picking_type_id or not op.kc_semi_location_id:
            return
        product = ticket.product_id
        if not product:
            _logger.info('KC semi ticket %s: sin producto, no se crea movimiento de stock.', ticket.name)
            return
        if not product.is_storable:
            _logger.info('KC semi ticket %s: producto no inventariable, no se crea picking.', ticket.name)
            return
        if product.tracking == 'serial':
            _logger.info(
                'KC semi ticket %s: trazabilidad por número de serie; complete el albarán manualmente si aplica.',
                ticket.name,
            )
            return
        pt = op.kc_semi_picking_type_id
        if pt.code != 'internal':
            _logger.warning(
                'KC semi ticket %s: el tipo «%s» no es transferencia interna; no se crea picking.',
                ticket.name,
                pt.display_name,
            )
            return
        company = ticket.company_id
        if pt.company_id and pt.company_id != company:
            _logger.warning(
                'KC semi ticket %s: la compañía del tipo de operación no coincide con la del ticket; omitiendo picking.',
                ticket.name,
            )
            return
        mo = ticket.production_id
        loc_src = pt.default_location_src_id
        loc_dest = op.kc_semi_location_id
        if not loc_src or not loc_dest:
            _logger.warning('KC semi ticket %s: falta ubicación origen o destino; omitiendo picking.', ticket.name)
            return
        for loc in (loc_src, loc_dest):
            if loc.company_id and loc.company_id != company:
                _logger.warning(
                    'KC semi ticket %s: ubicación «%s» es de otra compañía; omitiendo picking.',
                    ticket.name,
                    loc.display_name,
                )
                return
        product_uom = product.uom_id
        qty_product_uom = ticket.uom_id._compute_quantity(
            ticket.quantity,
            product_uom,
            rounding_method='HALF-UP',
        )
        if float_is_zero(qty_product_uom, precision_rounding=product_uom.rounding):
            return
        picking = self.env['stock.picking'].create({
            'picking_type_id': pt.id,
            'location_id': loc_src.id,
            'location_dest_id': loc_dest.id,
            'origin': _('%s | %s') % (ticket.name, mo.name),
            'company_id': company.id,
            'move_ids': [(0, 0, {
                'name': ticket.name,
                'product_id': product.id,
                'product_uom': product_uom.id,
                'product_uom_qty': qty_product_uom,
                'location_id': loc_src.id,
                'location_dest_id': loc_dest.id,
                'company_id': company.id,
            })],
        })
        move = picking.move_ids[0]
        picking.action_confirm()
        move._set_quantity_done(move.product_uom_qty)
        if product.tracking == 'lot' and (pt.use_create_lots or pt.use_existing_lots):
            for ml in move.move_line_ids:
                if not ml.lot_id and not ml.lot_name:
                    ml.lot_name = ticket.name
        move.move_line_ids.picked = True
        move.picked = True
        if not self.env.context.get('skip_sanity_check', False):
            picking._sanity_check()
        picking.with_context(cancel_backorder=True, skip_backorder=True)._action_done()
        ticket.write({'stock_move_id': move.id})

    def _kc_semi_ticket_should_print(self):
        """Etiqueta semi: requiere flag en la operación (LdM) e impresora de red en el centro de trabajo."""
        self.ensure_one()
        op = self.operation_id
        wc = self.workcenter_id
        if not op or not op.kc_semi_print_ticket:
            return False
        if not wc or not wc.kc_label_network_printer_id:
            return False
        return True

    def action_reprint(self):
        self.ensure_one()
        if not self._kc_semi_ticket_should_print():
            raise UserError(_(
                'La reimpresión de la etiqueta semi solo está disponible si la operación tiene activo '
                '«Imprimir ticket» y el centro de trabajo tiene una impresora de red de etiquetas configurada.'
            ))
        self.write({
            'printed_at': fields.Datetime.now(),
            'print_count': self.print_count + 1,
        })
        return self._report_print()

    def _report_print(self):
        self.ensure_one()
        if not self._kc_semi_ticket_should_print():
            _logger.info(
                'KC semi ticket: impresión omitida (operación sin «Imprimir ticket» o sin impresora en WC) ticket=%s',
                self.id,
            )
            return True
        report = self.env.ref('kc_mrp_wizard.action_report_mrp_semi_ticket', raise_if_not_found=False)
        if not report:
            return True
        return report.report_action(self)

    @api.constrains('workorder_id', 'workcenter_id', 'operation_id', 'company_id')
    def _check_workorder_coherence(self):
        for rec in self:
            wo = rec.workorder_id
            if wo.production_id != rec.production_id:
                raise ValidationError(
                    _('La orden de trabajo no pertenece a la orden de fabricación del ticket (%s).') % (rec.name,)
                )
            if rec.workcenter_id and wo.workcenter_id and rec.workcenter_id != wo.workcenter_id:
                raise ValidationError(
                    _('El centro del ticket debe coincidir con el de la orden de trabajo (%s).') % (rec.name,)
                )
