# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class MrpTabletConfirmBatchLotBadQtyWizard(models.TransientModel):
    """Producción manual: cantidad editable y lote existente o nuevo (sin marcar baja calidad)."""

    _name = 'mrp.tablet.confirm.batch.lot.bad.qty.wizard'
    _description = 'Asistente: producción manual por lote (cantidad editable)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
        required=True,
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        related='workorder_id.production_id',
        readonly=True,
    )
    qty_to_produce = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        required=True,
        help='Cantidad a registrar en este paso. No puede superar lo pendiente por producir en la orden.',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        domain="[('product_id', '=', product_id), ('kc_prelabel_production_id', '=', production_id), ('kc_prelabel_state', '!=', 'pending')]",
        help='Solo lotes vinculados a esta orden de fabricación. Vacío = crear lote nuevo ligado a la MO.',
    )

    @api.onchange('product_id', 'production_id')
    def _onchange_lot_domain_mo(self):
        if self.product_id and self.production_id:
            return {
                'domain': {
                    'lot_id': [
                        ('product_id', '=', self.product_id.id),
                        ('kc_prelabel_production_id', '=', self.production_id.id),
                        ('kc_prelabel_state', '!=', 'pending'),
                    ],
                },
            }
        return {'domain': {'lot_id': []}}

    def action_confirm(self):
        """Registra producción PT con cantidad manual (misma lógica de inventario que «Crear lote»)."""
        self.ensure_one()
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        if wo.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de registrar producción manual.'))
        mo = wo.production_id
        qty_to_produce = wo._tablet_normalize_production_qty(self.qty_to_produce)
        if qty_to_produce <= 0:
            raise UserError(_('La cantidad debe ser mayor que cero.'))
        rounding = mo.product_uom_id.rounding
        remaining = wo._tablet_normalize_production_qty(mo.product_qty - mo.qty_produced)
        if float_compare(qty_to_produce, remaining, precision_rounding=rounding) > 0:
            raise UserError(
                _('La cantidad (%(qty)s %(uom)s) no puede superar lo pendiente por producir (%(rem)s %(uom)s).')
                % {
                    'qty': qty_to_produce,
                    'rem': remaining,
                    'uom': mo.product_uom_id.name,
                }
            )
        if self.lot_id:
            if self.lot_id.product_id != self.product_id:
                raise UserError(_('El lote seleccionado no corresponde al producto de esta orden.'))
            if self.lot_id.kc_prelabel_production_id != mo:
                raise UserError(
                    _('El lote «%s» no pertenece a la orden de fabricación %s.')
                    % (self.lot_id.name, mo.name)
                )
            if self.lot_id.kc_prelabel_state == 'pending':
                raise UserError(
                    _('El lote «%s» es una pre-etiqueta pendiente. Use «Escanear pre-etiqueta» para producirla.')
                    % self.lot_id.name
                )
        workcenter = wo.workcenter_id
        return wo._tablet_create_batch_lot_impl(
            qty_to_produce,
            self.employee_id,
            workcenter,
            lot=self.lot_id or None,
            is_bad_quality=False,
        )
