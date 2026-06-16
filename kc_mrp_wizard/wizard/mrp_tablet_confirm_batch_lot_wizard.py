# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class MrpTabletConfirmBatchLotWizard(models.TransientModel):
    _name = 'mrp.tablet.confirm.batch.lot.wizard'
    _description = 'Confirmar datos del lote antes de grabar (tablet)'

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
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    qty_to_produce = fields.Float(
        string='Cantidad (este lote)',
        digits='Product Unit of Measure',
        readonly=True,
        help='Tamaño del fardo según cantidad base de la LdM; el último lote puede ser menor.',
    )
    batches_remaining_hint = fields.Char(
        string='Lotes pendientes (aprox.)',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
        readonly=True,
    )

    def action_confirm(self):
        """Confirmar y crear el lote llamando al método del workorder."""
        self.ensure_one()
        if not self.workorder_id.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        return self.workorder_id.action_tablet_create_batch_lot()
