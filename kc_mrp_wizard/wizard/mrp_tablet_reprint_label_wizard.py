# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpTabletReprintLabelWizard(models.TransientModel):
    _name = 'mrp.tablet.reprint.label.wizard'
    _description = 'Consultar lote y re-imprimir etiqueta (tablet)'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        readonly=True,
    )
    lot_name_manual = fields.Char(
        string='Número de lote',
        help='Escriba el número de lote y pulse «Buscar».',
    )
    gs1_barcode_input = fields.Char(
        string='Escanear QR GS1',
        help='Escanee el código GS1 de la etiqueta (Enter o «Buscar QR»).',
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        readonly=True,
    )
    product_id = fields.Many2one(
        related='lot_id.product_id',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        related='product_id.uom_id',
        readonly=True,
    )
    kc_prelabel_production_id = fields.Many2one(
        related='lot_id.kc_prelabel_production_id',
        readonly=True,
    )
    kc_prelabel_state = fields.Selection(
        related='lot_id.kc_prelabel_state',
        readonly=True,
    )
    kc_prelabel_qty = fields.Float(
        related='lot_id.kc_prelabel_qty',
        readonly=True,
        digits='Product Unit of Measure',
    )
    kc_prelabel_shift = fields.Selection(
        related='lot_id.kc_prelabel_shift',
        readonly=True,
    )
    kc_prelabel_workcenter_id = fields.Many2one(
        related='lot_id.kc_prelabel_workcenter_id',
        readonly=True,
    )
    qty_on_hand = fields.Float(
        string='Cantidad a mano',
        compute='_compute_qty_on_hand',
        digits='Product Unit of Measure',
        readonly=True,
    )
    kc_last_reprint_employee_id = fields.Many2one(
        related='lot_id.kc_last_reprint_employee_id',
        readonly=True,
    )
    kc_last_reprint_date = fields.Datetime(
        related='lot_id.kc_last_reprint_date',
        readonly=True,
    )
    kc_reprint_count = fields.Integer(
        related='lot_id.kc_reprint_count',
        readonly=True,
    )
    kc_allow_reprint_permission = fields.Boolean(
        string='Permiso reimpresión',
        compute='_compute_reprint_state',
    )
    kc_reprint_allowed = fields.Boolean(
        string='Puede reimprimir',
        compute='_compute_reprint_state',
    )
    reprint_info_message = fields.Char(
        string='Aviso reimpresión',
        compute='_compute_reprint_state',
    )

    @api.depends('lot_id', 'lot_id.product_qty')
    def _compute_qty_on_hand(self):
        for wizard in self:
            wizard.qty_on_hand = wizard.lot_id.product_qty if wizard.lot_id else 0.0

    @api.depends(
        'lot_id',
        'lot_id.kc_prelabel_state',
        'lot_id.kc_prelabel_production_id',
        'employee_id.kc_tablet_allow_reprint_label',
        'workorder_id.production_id',
    )
    def _compute_reprint_state(self):
        for wizard in self:
            wizard.kc_allow_reprint_permission = bool(
                wizard.employee_id.kc_tablet_allow_reprint_label
            )
            wizard.kc_reprint_allowed = False
            wizard.reprint_info_message = False
            if not wizard.lot_id:
                continue
            if not wizard.kc_allow_reprint_permission:
                wizard.reprint_info_message = _(
                    'No tiene permiso para re-imprimir etiquetas.'
                )
                continue
            try:
                wizard.lot_id._kc_tablet_assert_can_reprint_label()
            except UserError as err:
                wizard.reprint_info_message = err.args[0] if err.args else _(
                    'No se puede reimprimir este lote.'
                )
                continue
            mo = wizard.workorder_id.production_id
            if wizard.lot_id.kc_prelabel_production_id != mo:
                wizard.reprint_info_message = _(
                    'El lote «%s» pertenece a la orden %s; esta operación es de %s.'
                ) % (
                    wizard.lot_id.name,
                    wizard.lot_id.kc_prelabel_production_id.name,
                    mo.name,
                )
                continue
            wizard.kc_reprint_allowed = True

    def _reopen_self_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Consultar lote'),
            'context': dict(self.env.context),
        }

    def _bump_focus_token(self):
        self.ensure_one()
        return (self.kc_focus_token or 0) + 1

    def _gs1_scan_raw(self):
        self.ensure_one()
        raw = (self.gs1_barcode_input or '').strip()
        if not raw:
            raw = (self.env.context.get('kc_gs1_barcode_scan') or '').strip()
        return raw

    def _find_lot_for_consult(self, lot_name):
        """Busca lote por nombre sin validar reimpresión ni MO."""
        self.ensure_one()
        name = (lot_name or '').strip()
        if not name:
            raise UserError(_('Indique el número de lote o escanee un QR GS1.'))
        company = self.workorder_id.company_id
        Lot = self.env['stock.lot']
        lots = Lot.search([
            ('name', '=', name),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ])
        if not lots:
            raise UserError(_('No se encontró el lote «%s».') % name)
        if len(lots) > 1:
            raise UserError(
                _('El código «%s» coincide con varios lotes. Contacte al administrador.')
                % name
            )
        return lots[0]

    def _apply_lot_result(self, lot):
        self.ensure_one()
        self.write({
            'lot_id': lot.id,
            'lot_name_manual': lot.name,
            'gs1_barcode_input': False,
            'kc_focus_token': self._bump_focus_token(),
        })

    def action_search_lot_manual(self):
        self.ensure_one()
        lot = self._find_lot_for_consult(self.lot_name_manual)
        self._apply_lot_result(lot)
        return self._reopen_self_action()

    def action_search_lot_gs1(self):
        self.ensure_one()
        raw = self._gs1_scan_raw()
        if not raw:
            raise UserError(_('Escanee o pegue un código QR GS1.'))
        if not (self.gs1_barcode_input or '').strip():
            self.gs1_barcode_input = raw
        lot_name = self.env['stock.lot'].kc_tablet_resolve_prelabel_scan_to_lot_name(raw)
        if not lot_name:
            raise UserError(_('No se pudo extraer el número de lote del QR GS1.'))
        lot = self._find_lot_for_consult(lot_name)
        self._apply_lot_result(lot)
        return self._reopen_self_action()

    def _assert_employee_can_reprint(self):
        self.ensure_one()
        if not self.employee_id or not self.employee_id.kc_tablet_allow_reprint_label:
            raise UserError(_('No tiene permiso para re-imprimir etiquetas.'))

    def _assert_lot_can_reprint(self, lot):
        self.ensure_one()
        lot._kc_tablet_assert_can_reprint_label()
        mo = self.workorder_id.production_id
        if lot.kc_prelabel_production_id != mo:
            raise UserError(
                _('El lote «%s» pertenece a la orden %s; esta operación es de %s.')
                % (lot.name, lot.kc_prelabel_production_id.name, mo.name)
            )

    def action_reprint_label(self):
        self.ensure_one()
        wo = self.workorder_id
        lot = self.lot_id
        if not lot:
            if self.lot_name_manual:
                lot = self._find_lot_for_consult(self.lot_name_manual)
            elif self._gs1_scan_raw():
                lot_name = self.env['stock.lot'].kc_tablet_resolve_prelabel_scan_to_lot_name(
                    self._gs1_scan_raw()
                )
                lot = self._find_lot_for_consult(lot_name)
            else:
                raise UserError(_('Busque un lote antes de reimprimir.'))
            self.lot_id = lot.id

        self._assert_employee_can_reprint()
        self._assert_lot_can_reprint(lot)

        printer = wo.workcenter_id.kc_label_network_printer_id
        if not printer:
            raise UserError(
                _('Configure la impresora de etiquetas en el centro «%s».')
                % wo.workcenter_id.display_name
            )

        lot._kc_tablet_record_label_reprint(self.employee_id)
        shift = lot.kc_prelabel_shift if lot.kc_prelabel_state == 'pending' else None
        workcenter = lot.kc_prelabel_workcenter_id or wo.workcenter_id
        res = lot.kc_send_lot_label_to_network_printer(
            printer,
            workcenter=workcenter,
            shift_letter=shift,
        )
        if not res.get('success'):
            raise UserError(res.get('error') or _('No se pudo enviar la etiqueta a la impresora.'))

        _logger.info(
            'KC tablet: reimpresión lote %s por empleado %s (WO %s)',
            lot.name,
            self.employee_id.display_name if self.employee_id else '-',
            wo.id,
        )
        return wo._tablet_action_return_kanban_single_wo(wo.workcenter_id)
