# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class MrpTabletWizard(models.TransientModel):
    _name = 'mrp.tablet.wizard'
    _description = 'Asistente tablet — Producción por lote (fardo)'

    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required=True,
        ondelete='cascade',
    )
    pin_input = fields.Char(
        string='PIN',
        help='PIN del empleado (no se almacena).',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        readonly=True,
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        readonly=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        readonly=True,
    )
    batch_qty = fields.Float(
        string='Cantidad por lote',
        digits='Product Unit of Measure',
        readonly=True,
    )
    state = fields.Selection([
        ('pin', 'Identificación'),
        ('production', 'Producción'),
    ], string='Estado', default='pin', required=True)

    def action_validate_pin(self):
        """Valida PIN y que el empleado esté permitido en el workcenter."""
        self.ensure_one()
        if not self.pin_input or not self.pin_input.strip():
            raise UserError(_('Introduzca el PIN.'))
        employee = self._validate_pin(self.workcenter_id, self.pin_input.strip())
        if not employee:
            raise UserError(_('PIN inválido.'))
        # employee_ids (mrp_workorder): si tiene valores, solo esos empleados pueden operar
        if self.workcenter_id.employee_ids and employee not in self.workcenter_id.employee_ids:
            raise UserError(_('Empleado no autorizado para este centro de trabajo.'))
        wo = self._get_active_workorder(self.workcenter_id)
        if not wo:
            raise UserError(_('No hay orden de trabajo activa para este centro.'))
        mo = wo.production_id
        batch_qty = self._get_batch_qty(mo, self.workcenter_id)
        self.write({
            'employee_id': employee.id,
            'production_id': mo.id,
            'workorder_id': wo.id,
            'batch_qty': batch_qty,
            'state': 'production',
            'pin_input': False,
        })
        return True

    def _validate_pin(self, workcenter, pin):
        """Busca empleado por PIN (comparación segura). No registrar PIN en logs."""
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', 'in', [False, workcenter.company_id.id]),
        ])
        for emp in employees:
            if emp.check_pin(pin):
                return emp
        return self.env['hr.employee']

    def _get_active_workorder(self, workcenter):
        """WO activa: primero en progress, luego ready; orden prioridad desc, fecha asc, id asc."""
        domain_progress = [
            ('workcenter_id', '=', workcenter.id),
            ('state', '=', 'progress'),
            ('production_id.state', 'in', ('confirmed', 'progress', 'to_close')),
        ]
        wo = self.env['mrp.workorder'].search(
            domain_progress, order='priority desc, date_start asc, id asc', limit=1
        )
        if wo:
            return wo
        domain_ready = [
            ('workcenter_id', '=', workcenter.id),
            ('state', '=', 'ready'),
            ('production_id.state', 'in', ('confirmed', 'progress', 'to_close')),
        ]
        return self.env['mrp.workorder'].search(
            domain_ready, order='priority desc, date_start asc, id asc', limit=1
        )

    def _get_batch_qty(self, production, workcenter):
        """Cantidad por lote: según la lista de materiales (BOM) de la MO, campo product_qty (cantidad más pequeña a producir)."""
        if production.bom_id and production.bom_id.product_qty > 0:
            return production.product_uom_id._compute_quantity(
                production.bom_id.product_qty,
                production.bom_id.product_uom_id,
                rounding_method='HALF-UP',
            )
        return production.product_qty

    def action_create_batch_lot(self):
        """Crea lote (fardo), registra producción parcial y genera ticket + impresión."""
        self.ensure_one()
        if not self.employee_id or not self.workorder_id or not self.production_id:
            raise UserError(_('Sesión inválida. Vuelva a identificar con PIN.'))
        workcenter = self.workcenter_id
        wo = self.workorder_id
        mo = self.production_id
        # Revalidar empleado (employee_ids en workcenter, mrp_workorder)
        if workcenter.employee_ids and self.employee_id not in workcenter.employee_ids:
            raise UserError(_('Empleado no autorizado para este centro.'))
        # La ubicación de consumo es la de la MO (location_src_id), ya configurada en la orden.
        rounding = mo.product_uom_id.rounding
        remaining = mo.product_qty - mo.qty_produced
        if remaining <= 0:
            raise UserError(_('La orden ya está completa. No hay cantidad por producir.'))
        if float_compare(self.batch_qty, remaining, precision_rounding=rounding) > 0:
            qty_to_produce = remaining
        else:
            qty_to_produce = self.batch_qty
        # Lock (evitar doble ejecución): bloquear el registro en la transacción
        self.env.cr.execute('SELECT 1 FROM mrp_workorder WHERE id = %s FOR UPDATE', [wo.id])
        # Crear lote PT (nombre por secuencia stock.lot.serial si existe)
        lot_vals = {
            'product_id': mo.product_id.id,
            'company_id': mo.company_id.id,
        }
        lot = self.env['stock.lot'].create(lot_vals)
        # Registrar producción parcial: qty_producing + lote, actualizar movimientos y validar
        mo.write({
            'lot_producing_id': lot.id,
            'qty_producing': mo.qty_produced + qty_to_produce,
        })
        mo._set_qty_producing(False)
        finish_move = mo.move_finished_ids.filtered(
            lambda m: m.product_id == mo.product_id and m.state not in ('done', 'cancel')
        )
        if not finish_move:
            raise UserError(_('No se encontró el movimiento de producto terminado.'))
        finish_move.picked = True
        raw_moves = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        raw_moves.picked = True
        # Validar movimientos (pueden dividirse en done + backorder si qty < total)
        finish_move.with_context(skip_mo_check=True)._action_done(cancel_backorder=True)
        raw_moves.with_context(skip_mo_check=True)._action_done(cancel_backorder=True)
        # Actualizar qty_produced en la WO sin cerrarla
        wo.with_context(bypass_duration_calculation=True).write({
            'qty_produced': wo.qty_produced + qty_to_produce,
        })
        # Dejar MO lista para siguiente lote
        mo.write({
            'qty_producing': 0.0,
            'lot_producing_id': False,
        })
        # Crear ticket
        ticket = self.env['mrp.batch.ticket'].create({
            'production_id': mo.id,
            'workorder_id': wo.id,
            'workcenter_id': workcenter.id,
            'product_id': mo.product_id.id,
            'lot_id': lot.id,
            'qty': qty_to_produce,
            'employee_id': self.employee_id.id,
        })
        ticket.write({'printed_at': fields.Datetime.now(), 'print_count': 1})
        # Impresión
        try:
            ticket._report_print()
        except Exception:
            pass
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.batch.ticket',
            'view_mode': 'form',
            'res_id': ticket.id,
            'target': 'new',
        }
