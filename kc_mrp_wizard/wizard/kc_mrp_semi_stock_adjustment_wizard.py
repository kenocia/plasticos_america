# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class KcMrpSemiStockAdjustmentWizard(models.TransientModel):
    _name = 'kc.mrp.semi.stock.adjustment.wizard'
    _description = 'Asistente: salida / ajuste de inventario semi (MO)'

    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='production_id.company_id',
    )
    line_ids = fields.One2many(
        'kc.mrp.semi.stock.adjustment.wizard.line',
        'wizard_id',
        string='Líneas',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mo = self.env['mrp.production'].browse(self.env.context.get('default_production_id'))
        if mo and mo.exists():
            res['production_id'] = mo.id
        return res

    def _kc_scrap_location(self):
        self.ensure_one()
        mo = self.production_id
        return self.env['stock.location'].search([
            ('scrap_location', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', mo.company_id.id),
        ], limit=1, order='company_id desc, id')

    def _kc_internal_picking_type(self):
        self.ensure_one()
        mo = self.production_id
        wh = mo.picking_type_id.warehouse_id
        if not wh:
            wh = self.env['stock.warehouse'].search([
                ('company_id', '=', mo.company_id.id),
            ], limit=1)
        if wh and wh.int_type_id:
            return wh.int_type_id
        return self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            '|', ('company_id', '=', False), ('company_id', '=', mo.company_id.id),
        ], limit=1)

    def action_apply(self):
        self.ensure_one()
        mo = self.production_id
        if mo.state == 'cancel':
            raise UserError(_('No se pueden registrar ajustes en una orden cancelada.'))
        lines = self.line_ids.filtered(
            lambda l: not float_is_zero(
                l.quantity,
                precision_rounding=l.product_uom_id.rounding if l.product_uom_id else 1e-6,
            )
        )
        if not lines:
            raise UserError(_('Indique al menos una línea con cantidad mayor que cero.'))
        for line in lines:
            if not line.ticket_id:
                raise UserError(
                    _(
                        'Cada línea con cantidad debe tener un «Ticket» seleccionado '
                        '(así se rellenan producto, UdM y ubicación de origen).'
                    )
                )
            if not line.product_id or not line.product_uom_id:
                raise UserError(
                    _('El ticket %s no tiene producto semi definido; revise el ticket.')
                    % (line.ticket_id.display_name,)
                )
            if not line.location_src_id:
                raise UserError(
                    _('Indique la ubicación de origen para el ticket %s (o vuelva a elegir el ticket).')
                    % (line.ticket_id.display_name,)
                )
        scrap_loc = self._kc_scrap_location()
        picking_type = self._kc_internal_picking_type()
        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación «Transferencia interna» para la compañía.'))
        AdjustmentLine = self.env['kc.mrp.production.semi.adjustment.line']
        for line in lines:
            line._kc_validate_line(scrap_loc)
        for line in lines:
            dest = scrap_loc if line.is_scrap_desecho else line.location_dest_id
            product = line.product_id
            if line.is_scrap_desecho and not dest:
                raise UserError(_('No hay ubicación de merma (scrap) configurada para esta compañía.'))
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': line.location_src_id.id,
                'location_dest_id': dest.id,
                'origin': _('%s | Ajuste semi') % (mo.name,),
                'company_id': mo.company_id.id,
                'move_ids': [(0, 0, {
                    'name': _('Ajuste semi %s') % (product.display_name,),
                    'product_id': product.id,
                    'product_uom': line.product_uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': line.location_src_id.id,
                    'location_dest_id': dest.id,
                    'company_id': mo.company_id.id,
                    'kc_semi_adjustment_production_id': mo.id,
                })],
            })
            picking.action_confirm()
            move = picking.move_ids[:1]
            if not move:
                raise UserError(
                    _('No se generó el movimiento de stock en el albarán %s.') % picking.display_name
                )
            move = move[0]
            move._set_quantity_done(line.quantity)
            if product.tracking == 'lot':
                if not line.lot_id:
                    raise UserError(_('Debe indicar el lote para el producto %s.') % (product.display_name,))
                for ml in move.move_line_ids:
                    ml.lot_id = line.lot_id
            move.move_line_ids.picked = True
            move.picked = True
            if not self.env.context.get('skip_sanity_check', False):
                picking._sanity_check()
            picking.with_context(cancel_backorder=True, skip_backorder=True)._action_done()
            AdjustmentLine.create({
                'production_id': mo.id,
                'stock_move_id': move.id,
                'product_uom_id': line.product_uom_id.id,
                'quantity': line.quantity,
                'is_scrap_desecho': line.is_scrap_desecho,
            })
        mo.kc_semi_ticket_ids.invalidate_recordset(['kc_semi_qty_available_in_semi'])
        return {'type': 'ir.actions.act_window_close'}


class KcMrpSemiStockAdjustmentWizardLine(models.TransientModel):
    _name = 'kc.mrp.semi.stock.adjustment.wizard.line'
    _description = 'Línea asistente salida semi'

    wizard_id = fields.Many2one(
        'kc.mrp.semi.stock.adjustment.wizard',
        string='Asistente',
        required=True,
        ondelete='cascade',
    )
    production_id = fields.Many2one(
        related='wizard_id.production_id',
    )
    ticket_id = fields.Many2one(
        'mrp.semi.ticket',
        string='Ticket',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto semi',
        domain="[('is_storable', '=', True)]",
        readonly=True,
        help='Se rellena al elegir el ticket; obligatorio al validar si la cantidad es mayor que cero.',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        help='Se rellena al elegir el ticket; obligatorio al validar si la cantidad es mayor que cero.',
    )
    quantity = fields.Float(
        string='Cant. Sacar',
        digits='Product Unit of Measure',
        default=0.0,
    )
    location_src_id = fields.Many2one(
        'stock.location',
        string='U. Origen',
        domain="['&', ('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=False,
        help='Se rellena al elegir el ticket según la operación; obligatorio al validar si la cantidad es mayor que cero.',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=False,
    )
    is_scrap_desecho = fields.Boolean(
        string='Merma',
        default=False,
        help='Marque si el semi no pasó a producción y debe salir a la ubicación de merma de la compañía.',
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='U. Destino',
        domain="['&', '|', '|', ('usage', '=', 'inventory'), ('scrap_location', '=', True), ('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=False,
        help='Ubicación destino: física interna, merma (scrap) o inventario (ajuste / pérdida). Obligatorio si no marca «Merma» con destino automático.',
    )
    company_id = fields.Many2one(
        related='wizard_id.company_id',
    )
    kc_available_qty_help = fields.Float(
        string='Disponible',
        compute='_compute_kc_available_qty_help',
        digits='Product Unit of Measure',
        help='Referencia de cantidad en origen según cuantos (y lote si aplica).',
    )

    @api.depends('product_id', 'location_src_id', 'lot_id', 'production_id')
    def _compute_kc_available_qty_help(self):
        Quant = self.env['stock.quant']
        for line in self:
            line.kc_available_qty_help = 0.0
            if not line.product_id or not line.location_src_id:
                continue
            company = line.company_id or line.production_id.company_id
            if not company:
                continue
            domain = [
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', line.location_src_id.ids),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ]
            if line.product_id.tracking == 'lot' and line.lot_id:
                domain.append(('lot_id', '=', line.lot_id.id))
            elif line.product_id.tracking == 'lot' and not line.lot_id:
                continue
            quants = Quant.search(domain)
            line.kc_available_qty_help = sum(quants.mapped('quantity'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            if self.product_id.tracking != 'lot':
                self.lot_id = False

    @api.onchange('ticket_id')
    def _onchange_ticket_id(self):
        if not self.ticket_id:
            return
        t = self.ticket_id
        self.product_id = t.product_id
        self.product_uom_id = t.uom_id or (t.product_id.uom_id if t.product_id else False)
        op = t.operation_id
        self.location_src_id = op.kc_semi_location_id if op else False
        lots = t.stock_move_id.move_line_ids.mapped('lot_id') if t.stock_move_id else self.env['stock.lot']
        if len(lots) == 1:
            self.lot_id = lots[0]
        else:
            self.lot_id = False
        uom = self.product_uom_id or (t.product_id.uom_id if t.product_id else False)
        if uom and t.kc_semi_qty_available_in_semi and not float_is_zero(
            t.kc_semi_qty_available_in_semi, precision_rounding=uom.rounding
        ):
            self.quantity = t.kc_semi_qty_available_in_semi

    @api.constrains('is_scrap_desecho', 'location_dest_id')
    def _check_dest_when_not_scrap(self):
        for line in self:
            if line.is_scrap_desecho:
                continue
            if not line.location_dest_id:
                raise ValidationError(_('Debe indicar la ubicación destino cuando no es merma por desecho.'))

    def _kc_validate_line(self, scrap_loc):
        self.ensure_one()
        product = self.product_id
        if not product.is_storable:
            raise UserError(_('El producto %s no es almacenable.') % product.display_name)
        if product.tracking == 'serial':
            raise UserError(_(
                'El producto %s está trazado por número de serie; gestione la salida desde inventario / albaranes.'
            ) % (product.display_name,))
        if self.is_scrap_desecho and not scrap_loc:
            raise UserError(_('No hay ubicación de merma configurada.'))
        if not self.is_scrap_desecho and not self.location_dest_id:
            raise UserError(_('Indique ubicación destino o marque merma por desecho.'))
        if not self.is_scrap_desecho and self.location_dest_id:
            d = self.location_dest_id
            if not (d.usage in ('internal', 'inventory') or d.scrap_location):
                raise UserError(_(
                    'La ubicación destino debe ser interna, de inventario (ajuste) o de merma (scrap).'
                ))
        mo = self.wizard_id.production_id
        if mo:
            self._kc_assert_locations_company(mo)
        if product.tracking == 'lot' and not self.lot_id:
            raise UserError(_('Indique el lote para %s.') % product.display_name)
        avail = self.kc_available_qty_help
        rounding = self.product_uom_id.rounding
        if float_compare(self.quantity, 0, precision_rounding=rounding) <= 0:
            raise UserError(_('La cantidad debe ser positiva (%s).') % product.display_name)
        if float_compare(self.quantity, avail, precision_rounding=rounding) > 0:
            raise UserError(_(
                'La cantidad a sacar (%(qty)s) supera lo disponible (%(avail)s %(uom)s) para %(product)s en la ubicación indicada.'
            ) % {
                'qty': self.quantity,
                'avail': avail,
                'uom': self.product_uom_id.name,
                'product': product.display_name,
            })

    def _kc_assert_locations_company(self, mo):
        self.ensure_one()
        comp = mo.company_id
        for loc in (self.location_src_id, self.location_dest_id):
            if not loc:
                continue
            if loc.company_id and loc.company_id != comp:
                raise UserError(_('La ubicación «%s» no pertenece a la compañía de la orden.') % loc.display_name)
        if self.lot_id and self.lot_id.company_id and self.lot_id.company_id != comp:
            raise UserError(_('El lote «%s» no pertenece a la compañía de la orden.') % self.lot_id.display_name)
