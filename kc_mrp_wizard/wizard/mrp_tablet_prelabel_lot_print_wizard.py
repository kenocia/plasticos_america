# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class MrpTabletPrelabelLotPrintWizard(models.TransientModel):
    _name = 'mrp.tablet.prelabel.lot.print.wizard'
    _description = 'Imprimir pre-etiquetas (tablet)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
    )
    workcenter_name = fields.Char(
        string='Centro de trabajo',
        related='workorder_id.workcenter_id.name',
        readonly=True,
    )
    workcenter_code = fields.Char(
        string='Código centro',
        related='workorder_id.workcenter_id.code',
        readonly=True,
        help='Se imprime en la etiqueta con turno y calidad (p. ej. P01-A1).',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado (pre-etiquetas)',
        help='Opcional al generar. Lista todos los empleados de hr.employee accesibles '
             'para el usuario (no se limita a los del centro de trabajo). '
             'Si se deja vacío, el lote se crea sin empleado; puede asignarlo después en el lote.',
    )
    label_count = fields.Integer(
        string='Número de etiquetas',
        default=1,
        required=True,
    )
    confirm_responsible = fields.Boolean(
        string='Confirmación responsable si se supera lo pendiente',
        help='Cuando la orden permite solo advertencia ante el exceso sobre pendiente, marque esto y confirme '
             'con un usuario con permiso de responsable de fabricación.',
    )
    prelabel_limit_policy = fields.Selection(
        related='workorder_id.production_id.kc_prelabel_limit_policy',
        readonly=True,
    )

    prelabel_shift = fields.Selection(
        selection=[('A', 'Turno A (día)'), ('B', 'Turno B (noche)')],
        string='Turno',
        default='A',
        required=True,
        help='Fijo A o B. Se imprime en la etiqueta con el código del centro (p. ej. P01-A1, P01-B2).',
    )

    @api.model
    def _default_prelabel_shift(self):
        return self.env['stock.lot']._kc_shift_letter_from_datetime()

    @api.model
    def default_get(self, fields_list):
        """No precargar empleado desde contexto tablet/PIN (campo vacío al abrir)."""
        res = super().default_get(fields_list)
        if 'employee_id' in fields_list:
            res['employee_id'] = False
        if 'prelabel_shift' in fields_list and not res.get('prelabel_shift'):
            res['prelabel_shift'] = self._default_prelabel_shift()
        return res
    production_id = fields.Many2one(
        related='workorder_id.production_id',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        related='production_id.product_uom_id',
        readonly=True,
    )
    prelabel_pending_count = fields.Integer(
        string='Pre-etiquetas pendientes',
        compute='_compute_prelabel_summary',
        readonly=True,
        help='Lotes impresos en estado «Pendiente de producir» (aún no escaneados en producción).',
    )
    prelabel_produced_count = fields.Integer(
        string='Etiquetas producidas',
        compute='_compute_prelabel_summary',
        readonly=True,
        help='Pre-etiquetas ya registradas como producción en esta orden.',
    )
    prelabel_to_generate_count = fields.Integer(
        string='Pendientes por generar (plan)',
        compute='_compute_prelabel_summary',
        readonly=True,
        help='Etiquetas que faltan imprimir según lo pendiente por fabricar en la OF y el tamaño de fardo (LdM), '
             'descontando la cantidad ya reservada en pre-etiquetas pendientes.',
    )
    @api.depends(
        'workorder_id',
        'workorder_id.production_id.product_qty',
        'workorder_id.production_id.qty_produced',
        'workorder_id.production_id.kc_prelabel_lot_ids',
        'workorder_id.production_id.kc_prelabel_lot_ids.kc_prelabel_state',
    )
    def _compute_prelabel_summary(self):
        Lot = self.env['stock.lot']
        for wizard in self:
            wizard.prelabel_pending_count = 0
            wizard.prelabel_produced_count = 0
            wizard.prelabel_to_generate_count = 0
            wo = wizard.workorder_id
            if not wo or not wo.production_id:
                continue
            mo = wo.production_id
            lots = Lot.search([('kc_prelabel_production_id', '=', mo.id)])
            pending = lots.filtered(lambda l: l.kc_prelabel_state == 'pending')
            produced = lots.filtered(lambda l: l.kc_prelabel_state == 'produced')
            wizard.prelabel_pending_count = len(pending)
            wizard.prelabel_produced_count = len(produced)
            remaining = mo._kc_prelabel_qty_remaining_to_make()
            reserved_qty = sum(pending.mapped('kc_prelabel_qty'))
            need_qty = wo._tablet_normalize_production_qty(remaining - reserved_qty)
            if float_compare(need_qty, 0.0, precision_rounding=mo.product_uom_id.rounding) > 0:
                wizard.prelabel_to_generate_count = wo._tablet_count_batches_for_qty(need_qty)
            else:
                wizard.prelabel_to_generate_count = 0

    def action_confirm(self):
        self.ensure_one()
        if self.label_count < 1:
            raise UserError(_('Indique al menos una etiqueta.'))
        if self.prelabel_shift not in ('A', 'B'):
            raise UserError(_('Seleccione el turno A (día) o B (noche).'))
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        mo = wo.production_id
        action, _eid, _session_employee, _workcenter = wo._tablet_validate_session()
        if action:
            return wo._tablet_return_with_refreshed_pin(action)
        wo._tablet_assert_mo_finished_product_lot_tracked()
        wo._tablet_assert_authorized_pt_lot_workcenter()
        if wo.state not in ('ready', 'waiting', 'progress', 'pending'):
            raise UserError(
                _('Pre-etiquetas: la orden de trabajo debe estar en progreso, lista, esperando componentes '
                  'o en espera de otra operación.')
            )
        force = self.confirm_responsible
        Lot = wo._tablet_sudo().env['stock.lot'].with_context(default_kc_employee_id=False)
        for _i in range(self.label_count):
            bundle = mo._kc_prelabel_bundle_qty_for_wo(wo)
            mo._kc_prelabel_assert_can_reserve_print(bundle, force_manager_confirm=force)
            lot_name = mo._kc_tablet_next_lot_name()
            lot_vals = {
                'product_id': mo.product_id.id,
                'company_id': mo.company_id.id,
                'name': lot_name,
                'kc_prelabel_production_id': mo.id,
                'kc_prelabel_qty': bundle,
                'kc_prelabel_state': 'pending',
                'kc_prelabel_shift': self.prelabel_shift,
                'kc_prelabel_workcenter_id': wo.workcenter_id.id,
            }
            if 'kc_employee_id' in Lot._fields:
                lot_vals['kc_employee_id'] = self.employee_id.id if self.employee_id else False
            lot = Lot.create(lot_vals)
            printer = wo.workcenter_id.kc_label_network_printer_id
            if printer:
                res = lot.kc_send_lot_label_to_network_printer(printer)
                if not res.get('success'):
                    _logger.warning(
                        'Pre-etiqueta: impresión red falló lote id=%s: %s',
                        lot.id, res.get('error'),
                    )
            else:
                _logger.warning(
                    'Pre-etiqueta: sin «Impresora etiquetas» en centro «%s» (lote %s). Configure el centro.',
                    wo.workcenter_id.display_name, lot.name,
                )
        return wo._tablet_action_return_kanban_single_wo(wo.workcenter_id)
