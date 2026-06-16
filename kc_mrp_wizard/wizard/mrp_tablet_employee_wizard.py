# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpTabletEmployeeWizard(models.TransientModel):
    _name = 'mrp.tablet.employee.wizard'
    _description = 'Asistente MRP — Seleccion de empleado'

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
    pin_masked = fields.Char(
        string='PIN',
        compute='_compute_pin_masked',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        # No se exige a nivel de BD; se valida en action_validate_pin.
        required=False,
        domain="[('id', 'in', allowed_employee_ids)]",
    )
    allowed_employee_ids = fields.Many2many(
        'hr.employee',
        compute='_compute_allowed_employee_ids',
        string='Empleados permitidos',
    )
    employee_line_ids = fields.One2many(
        'mrp.tablet.wizard.employee.line',
        'employee_wizard_id',
        string='Empleados',
    )

    @api.depends('workcenter_id', 'workcenter_id.employee_ids', 'workcenter_id.company_id')
    def _compute_allowed_employee_ids(self):
        for wiz in self:
            if not wiz.workcenter_id:
                wiz.allowed_employee_ids = self.env['hr.employee']
                continue
            wc = wiz.workcenter_id
            if wc.employee_ids:
                wiz.allowed_employee_ids = wc.employee_ids
            else:
                # Sin empleados asignados en el centro: nadie puede operar
                wiz.allowed_employee_ids = self.env['hr.employee']

    @api.depends('pin_input')
    def _compute_pin_masked(self):
        for wiz in self:
            wiz.pin_masked = '*' * len(wiz.pin_input or '')

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            if wiz.workcenter_id:
                wiz._update_employee_lines()
        return wizards

    @api.onchange('workcenter_id')
    def _onchange_workcenter_id_employee_lines(self):
        self._update_employee_lines()

    def _update_employee_lines(self):
        self.ensure_one()
        if not self.workcenter_id:
            self.employee_line_ids = [(5, 0, 0)]
            return
        wc = self.workcenter_id
        # Solo empleados asignados en el centro; si no hay ninguno, nadie puede operar
        allowed = wc.employee_ids or self.env['hr.employee']
        lines = [(5, 0, 0)]
        for emp in allowed:
            lines.append((0, 0, {'employee_id': emp.id}))
        self.employee_line_ids = lines
    
    # -------------------------------------------------------------------------
    # Paso PIN: helpers para mantener el wizard abierto al pulsar los botones
    # -------------------------------------------------------------------------

    def _action_reopen_pin_wizard(self):
        """Reabre el formulario de PIN para este wizard."""
        self.ensure_one()
        view = self.env.ref('kc_mrp_wizard.mrp_tablet_employee_pin_wizard_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asistente MRP — PIN'),
            'res_model': 'mrp.tablet.employee.wizard',
            'view_mode': 'form',
            'view_id': view.id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_pin_add_digit(self):
        self.ensure_one()
        digit = str(self.env.context.get('pin_digit') or '').strip()
        if not digit.isdigit() or len(digit) != 1:
            return self._action_reopen_pin_wizard()
        self.pin_input = '%s%s' % (self.pin_input or '', digit)
        return self._action_reopen_pin_wizard()

    def action_pin_backspace(self):
        self.ensure_one()
        self.pin_input = (self.pin_input or '')[:-1]
        return self._action_reopen_pin_wizard()

    def action_pin_clear(self):
        self.ensure_one()
        self.pin_input = False
        return self._action_reopen_pin_wizard()

    def action_validate_pin(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Seleccione un empleado.'))
        if not self.pin_input or not self.pin_input.strip():
            raise UserError(_('Introduzca el PIN.'))
        pin = self.pin_input.strip()
        if self.employee_id not in self.allowed_employee_ids:
            raise UserError(_('Empleado no autorizado para este centro de trabajo.'))
        if (self.employee_id.pin or '') != pin:
            raise UserError(_('PIN incorrecto para el empleado seleccionado.'))

        # Verificar que exista al menos una orden activa para este centro
        wo = self._get_active_workorder(self.workcenter_id)
        if not wo:
            raise UserError(
                _(
                    'No hay ninguna orden de trabajo abierta en este centro (estados: en progreso, listo, '
                    'esperando componentes o esperando otra operación) para un producto con trazabilidad «Por lotes».'
                )
            )

        # Actualizar marca de tiempo de autenticación en contexto de sesión tablet
        now = fields.Datetime.now()

        workcenter = self.workcenter_id
        domain = [
            ('workcenter_id', '=', workcenter.id),
            ('state', 'in', ('progress', 'ready', 'waiting', 'pending')),
            ('production_id.state', 'in', ('confirmed', 'progress', 'to_close')),
            ('production_id.product_id.tracking', '=', 'lot'),
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seleccione orden — %s') % workcenter.name,
            'res_model': 'mrp.workorder',
            'view_mode': 'kanban',
            'view_id': self.env.ref('kc_mrp_wizard.mrp_workorder_kanban_tablet_select').id,
            'domain': domain,
            'target': 'new',
            'context': {
                'tablet_employee_id': self.employee_id.id,
                'tablet_workcenter_id': workcenter.id,
                'tablet_last_pin_ts': now,
            },
        }

    def _get_active_workorder(self, workcenter):
        domain_base = [
            ('workcenter_id', '=', workcenter.id),
            ('production_id.state', 'in', ('confirmed', 'progress', 'to_close')),
            ('production_id.product_id.tracking', '=', 'lot'),
        ]
        for state in ('progress', 'ready', 'waiting', 'pending'):
            wo = self.env['mrp.workorder'].search(
                domain_base + [('state', '=', state)], order='id asc', limit=1
            )
            if wo:
                return wo
        return self.env['mrp.workorder']

    def action_cancel_pin(self):
        """Cancelar PIN y volver a la vista de centros de trabajo del asistente tablet."""
        action = self.env['ir.actions.act_window']._kc_tablet_action_workcenter_menu()
        action['target'] = 'main'
        return action

    def _get_batch_qty(self, production):
        if production.bom_id and production.bom_id.product_qty > 0:
            return production.product_uom_id._compute_quantity(
                production.bom_id.product_qty,
                production.bom_id.product_uom_id,
                rounding_method='HALF-UP',
            )
        return production.product_qty
