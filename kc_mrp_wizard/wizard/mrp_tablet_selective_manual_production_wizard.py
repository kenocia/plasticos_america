# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class MrpTabletSelectiveManualComponentLine(models.TransientModel):
    _name = 'mrp.tablet.selective.manual.component.line'
    _description = 'Línea de componente (producción manual selectiva tablet)'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'mrp.tablet.selective.manual.production.wizard',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    move_id = fields.Many2one(
        'stock.move',
        string='Movimiento',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        related='move_id.product_id',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        related='move_id.product_uom',
        string='UdM',
        readonly=True,
    )
    qty_to_consume = fields.Float(
        string='Cantidad LdM',
        compute='_compute_qty_to_consume',
        digits='Product Unit of Measure',
        readonly=True,
    )
    is_mandatory = fields.Boolean(
        string='Obligatorio',
        compute='_compute_is_mandatory',
        readonly=True,
    )
    consume = fields.Boolean(
        string='Consumir',
        default=True,
        help='Desmarque para no consumir este componente en este registro.',
    )

    @api.depends('move_id', 'move_id.bom_line_id', 'move_id.bom_line_id.kc_tablet_manual_consumption_optional', 'product_id.tracking')
    def _compute_is_mandatory(self):
        for line in self:
            bom_line = line.move_id.bom_line_id
            if bom_line:
                line.is_mandatory = not bom_line.kc_tablet_manual_consumption_optional
            else:
                line.is_mandatory = line.product_id.tracking in ('lot', 'serial')

    @api.depends('wizard_id.qty_to_produce', 'move_id')
    def _compute_qty_to_consume(self):
        for line in self:
            qty = 0.0
            wo = line.wizard_id.workorder_id
            if wo and line.move_id and line.wizard_id.qty_to_produce:
                for move, q in wo._tablet_compute_raw_batch_consumption_qtys(
                    line.move_id, line.wizard_id.qty_to_produce,
                ):
                    if move == line.move_id:
                        qty = q
                        break
            line.qty_to_consume = qty

    @api.onchange('consume')
    def _onchange_consume_mandatory(self):
        for line in self:
            if line.is_mandatory and not line.consume:
                line.consume = True
                return {
                    'warning': {
                        'title': _('Componente obligatorio'),
                        'message': _(
                            '«%s» debe consumirse (resina u otro componente marcado como obligatorio en la LdM).'
                        ) % line.product_id.display_name,
                    },
                }


class MrpTabletSelectiveManualProductionWizard(models.TransientModel):
    _name = 'mrp.tablet.selective.manual.production.wizard'
    _description = 'Producción manual con consumo selectivo (tablet)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        required=True,
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        related='workorder_id.production_id',
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        required=True,
        readonly=True,
    )
    qty_to_produce = fields.Float(
        string='Cantidad a producir',
        digits='Product Unit of Measure',
        required=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote existente',
        required=True,
        domain="[('product_id', '=', product_id), ('kc_prelabel_production_id', '=', production_id), ('kc_prelabel_state', '!=', 'pending')]",
        help='Solo lotes ya vinculados a esta orden. No se crea lote nuevo.',
    )
    line_ids = fields.One2many(
        'mrp.tablet.selective.manual.component.line',
        'wizard_id',
        string='Componentes',
    )

    def action_confirm(self):
        self.ensure_one()
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        if wo.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de registrar producción.'))
        mo = wo.production_id
        qty_to_produce = wo._tablet_normalize_production_qty(self.qty_to_produce)
        if qty_to_produce <= 0:
            raise UserError(_('La cantidad debe ser mayor que cero.'))
        rounding = mo.product_uom_id.rounding
        remaining = wo._tablet_normalize_production_qty(mo.product_qty - mo.qty_produced)
        if float_compare(qty_to_produce, remaining, precision_rounding=rounding) > 0:
            raise UserError(
                _('La cantidad (%(qty)s %(uom)s) no puede superar lo pendiente (%(rem)s %(uom)s).')
                % {'qty': qty_to_produce, 'rem': remaining, 'uom': mo.product_uom_id.name}
            )
        if not self.lot_id:
            raise UserError(_('Debe elegir un lote existente de esta orden.'))
        if self.lot_id.product_id != self.product_id:
            raise UserError(_('El lote no corresponde al producto de la orden.'))
        if self.lot_id.kc_prelabel_production_id != mo:
            raise UserError(
                _('El lote «%s» no pertenece a la orden %s.')
                % (self.lot_id.name, mo.name)
            )
        if self.lot_id.kc_prelabel_state == 'pending':
            raise UserError(
                _('Use «Escanear pre-etiqueta» para lotes pendientes de impresión.')
            )
        selected = self.line_ids.filtered('consume')
        if not selected:
            raise UserError(_('Seleccione al menos un componente a consumir.'))
        mandatory = self.line_ids.filtered('is_mandatory')
        missing_mandatory = mandatory.filtered(lambda l: not l.consume)
        if missing_mandatory:
            names = ', '.join(missing_mandatory.mapped('product_id.display_name'))
            raise UserError(
                _('Debe consumir los componentes obligatorios: %s.') % names
            )
        consume_move_ids = frozenset(selected.mapped('move_id').ids)
        return wo._tablet_create_batch_lot_impl(
            qty_to_produce,
            self.employee_id,
            wo.workcenter_id,
            lot=self.lot_id,
            is_bad_quality=False,
            consume_move_ids=consume_move_ids,
            allow_create_lot=False,
        )
