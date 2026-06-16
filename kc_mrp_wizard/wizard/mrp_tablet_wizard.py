# -*- coding: utf-8 -*-

import logging

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class MrpTabletWizard(models.TransientModel):
    _name = 'mrp.tablet.wizard'
    _description = 'Asistente MRP — Operatividad de produccion'

    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        readonly=True,
        required=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        readonly=True,
        required=True,
    )
    batch_qty = fields.Float(
        string='Cantidad por lote',
        digits='Product Unit of Measure',
        readonly=True,
    )


    # def action_create_batch_lot(self):
    #     """Crea lote (fardo), registra producción parcial y genera ticket + impresión."""
    #     self.ensure_one()
    #     if not self.employee_id or not self.workorder_id or not self.production_id:
    #         raise UserError(_('Sesión inválida. Vuelva a identificar con PIN.'))
    #     workcenter = self.workcenter_id
    #     wo = self.workorder_id
    #     mo = self.production_id
    #     if workcenter.employee_ids and self.employee_id not in workcenter.employee_ids:
    #         raise UserError(_('Empleado no autorizado para este centro.'))

    #     rounding = mo.product_uom_id.rounding
    #     remaining = mo.product_qty - mo.qty_produced
    #     _logger.info(
    #         'Tablet wizard create batch: WO id=%s MO id=%s mo.qty_produced=%s remaining=%s batch_qty=%s',
    #         wo.id, mo.id, mo.qty_produced, remaining, self.batch_qty,
    #     )
    #     if remaining <= 0:
    #         raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
    #     if float_compare(self.batch_qty, remaining, precision_rounding=rounding) > 0:
    #         qty_to_produce = remaining
    #     else:
    #         qty_to_produce = self.batch_qty

    #     self.env.cr.execute('SELECT 1 FROM mrp_workorder WHERE id = %s FOR UPDATE', [wo.id])
    #     move_finished_list = [
    #         (m.id, m.state, m.product_uom_qty, m.quantity)
    #         for m in mo.move_finished_ids
    #     ]
    #     _logger.info('Tablet wizard create batch: move_finished_ids %s', move_finished_list)

    #     lot_name = self.env['ir.sequence'].next_by_code('stock.lot.tablet') or (
    #         'LT-%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S')
    #     )
    #     lot_vals = {
    #         'product_id': mo.product_id.id,
    #         'company_id': mo.company_id.id,
    #         'name': lot_name,
    #     }
    #     lot = self.env['stock.lot'].create(lot_vals)
    #     _logger.info('Tablet wizard create batch: created lot id=%s name=%s', lot.id, lot.name)

    #     mo.invalidate_recordset(['qty_produced'])
    #     raw_to_update = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
    #     raw_to_update.invalidate_recordset(['unit_factor'])
    #     mo.write({
    #         'lot_producing_id': lot.id,
    #         'qty_producing': mo.qty_produced + qty_to_produce,
    #     })
    #     mo._set_qty_producing(False)
    #     wo._tablet_set_raw_consumption(raw_to_update, qty_to_produce)

    #     finish_move = mo.move_finished_ids.filtered(
    #         lambda m: m.product_id == mo.product_id and m.state not in ('done', 'cancel')
    #     )
    #     if not finish_move:
    #         _logger.warning(
    #             'Tablet wizard create batch: no finish_move WO=%s MO=%s move_finished=%s',
    #             wo.id, mo.id, [(m.id, m.state) for m in mo.move_finished_ids],
    #         )
    #         raise UserError(_('No se encontró el movimiento de producto terminado.'))
    #     finish_move = finish_move[0]
    #     _logger.info(
    #         'Tablet wizard create batch: finish_move id=%s state=%s product_uom_qty=%s move_line_ids=%s',
    #         finish_move.id, finish_move.state, finish_move.product_uom_qty,
    #         [(ml.id, ml.lot_id.id if ml.lot_id else None, ml.quantity) for ml in finish_move.move_line_ids],
    #     )

    #     wo._ensure_finished_move_line_has_lot(finish_move, lot, qty_to_produce)
    #     finish_move.picked = True
    #     raw_moves = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
    #     raw_moves.picked = True

    #     finish_move.with_context(skip_mo_check=True)._action_done(cancel_backorder=False)
    #     raw_moves.with_context(skip_mo_check=True)._action_done(cancel_backorder=False)

    #     wo.with_context(bypass_duration_calculation=True).write({
    #         'qty_produced': wo.qty_produced + qty_to_produce,
    #     })
    #     wo.invalidate_recordset(['qty_remaining'])
    #     mo.write({
    #         'qty_producing': 0.0,
    #         'lot_producing_id': False,
    #     })
    #     mo.invalidate_recordset(['qty_produced'])
    #     _logger.info(
    #         'Tablet wizard create batch: done WO=%s MO=%s mo.qty_produced=%s lot id=%s name=%s ticket qty=%s',
    #         wo.id, mo.id, mo.qty_produced, lot.id, lot.name, qty_to_produce,
    #     )

    #     ticket = self.env['mrp.batch.ticket'].create({
    #         'production_id': mo.id,
    #         'workorder_id': wo.id,
    #         'workcenter_id': workcenter.id,
    #         'product_id': mo.product_id.id,
    #         'lot_id': lot.id,
    #         'qty': qty_to_produce,
    #         'employee_id': self.employee_id.id,
    #     })
    #     ticket.write({'printed_at': fields.Datetime.now(), 'print_count': 1})
    #     try:
    #         ticket._report_print()
    #     except Exception:
    #         pass
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'mrp.batch.ticket',
    #         'view_mode': 'form',
    #         'res_id': ticket.id,
    #         'target': 'new',
    #     }
