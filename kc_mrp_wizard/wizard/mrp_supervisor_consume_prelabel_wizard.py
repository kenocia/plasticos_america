# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class MrpSupervisorConsumePrelabelLineWizard(models.TransientModel):
    _name = 'mrp.supervisor.consume.prelabel.line.wizard'
    _description = 'Línea pre-etiqueta (supervisor)'
    _order = 'sequence desc, id desc'

    wizard_id = fields.Many2one(
        'mrp.supervisor.consume.prelabel.wizard',
        string='Asistente',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote',
        required=True,
        ondelete='cascade',
    )
    lot_name = fields.Char(
        related='lot_id.name',
        string='Código de lote',
        readonly=True,
    )
    qty = fields.Float(
        string='Cantidad',
        related='lot_id.kc_prelabel_qty',
        readonly=True,
        digits='Product Unit of Measure',
    )


class MrpSupervisorConsumePrelabelWizard(models.TransientModel):
    _name = 'mrp.supervisor.consume.prelabel.wizard'
    _description = 'Registrar pre-etiquetas (supervisor, sin sesión tablet)'

    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de trabajo',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        readonly=True,
        help='Se fija con el primer escaneo; el resto debe ser de la misma MO y OT.',
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado Producción',
        help='Empleado que quedará en el ticket de lote (catálogo hr.employee). '
             'Por defecto el vinculado al usuario supervisor.',
    )
    lot_barcode = fields.Char(
        string='Código de lote',
        help='Escanee o pegue el código; pulse «Añadir a la lista» por cada pre-etiqueta.',
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
        help='Técnico: incrementa tras cada escaneo para devolver el foco al campo de código.',
    )
    line_ids = fields.One2many(
        'mrp.supervisor.consume.prelabel.line.wizard',
        'wizard_id',
        string='Pre-etiquetas a producir',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        wc_id = self.env.context.get('default_workcenter_id')
        if wc_id and 'workcenter_id' in fields_list and not res.get('workcenter_id'):
            res['workcenter_id'] = wc_id
        if 'employee_id' in fields_list and not res.get('employee_id'):
            res['employee_id'] = self.env.user.employee_id.id
        return res

    def _reopen_self_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Registrar pre-etiquetas (supervisor)'),
            'context': dict(self.env.context),
        }

    def _bump_scan_focus(self):
        self.ensure_one()
        return (self.kc_focus_token or 0) + 1

    def _next_prelabel_line_sequence(self):
        """Correlativo de línea: el escaneo más reciente lleva el número mayor (lista desc)."""
        self.ensure_one()
        if not self.line_ids:
            return 1
        return max(self.line_ids.mapped('sequence')) + 1

    def _error_return(self, message, title=None):
        self.ensure_one()
        self.write({'lot_barcode': False, 'kc_focus_token': self._bump_scan_focus()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or _('Atención'),
                'message': message,
                'type': 'danger',
                'sticky': True,
                'next': self._reopen_self_action(),
            },
        }

    def _lot_barcode_scan_raw(self):
        """Código escaneado: campo guardado o contexto (Enter/handheld antes del save)."""
        self.ensure_one()
        raw = (self.lot_barcode or '').strip()
        if not raw:
            raw = (self.env.context.get('kc_lot_barcode_scan') or '').strip()
        return raw

    def _lookup_lot_from_scan(self, raw):
        """Busca pre-etiqueta pendiente; si ya hay MO fijada, acota a esa orden."""
        self.ensure_one()
        mo = self.production_id if self.production_id else None
        return self.env['stock.lot'].kc_find_pending_prelabel_from_scan(
            raw,
            mo=mo,
            company=self.workcenter_id.company_id or self.env.company,
        )

    def _bind_workorder_from_lot(self, lot):
        """Primer escaneo: resuelve y guarda MO/OT; siguientes: deben coincidir."""
        self.ensure_one()
        Workorder = self.env['mrp.workorder']
        wo = Workorder.kc_resolve_workorder_for_prelabel_consume(lot, self.workcenter_id)
        if not self.workorder_id:
            self.write({
                'workorder_id': wo.id,
                'production_id': wo.production_id.id,
            })
            return wo
        if lot.kc_prelabel_production_id != self.production_id:
            raise UserError(
                _('Todas las pre-etiquetas deben ser de la orden de fabricación %s. '
                  'El lote «%s» pertenece a %s.')
                % (
                    self.production_id.name,
                    lot.name,
                    lot.kc_prelabel_production_id.name or '-',
                )
            )
        if wo != self.workorder_id:
            raise UserError(
                _('Todas las pre-etiquetas deben corresponder a la orden de trabajo %s. '
                  'El lote «%s» no encaja con la OT ya fijada en este registro.')
                % (self.workorder_id.display_name, lot.name)
            )
        return self.workorder_id

    def action_add_scan(self):
        self.ensure_one()
        try:
            raw = self._lot_barcode_scan_raw()
            if not raw:
                raise UserError(_('Escanee o pegue el código antes de añadir a la lista.'))
            lot = self._lookup_lot_from_scan(raw)
            self._bind_workorder_from_lot(lot)
            if self.line_ids.filtered(lambda l: l.lot_id == lot):
                raise UserError(_('El lote «%s» ya está en la lista.') % lot.name)
            self.env['mrp.supervisor.consume.prelabel.line.wizard'].create({
                'wizard_id': self.id,
                'lot_id': lot.id,
                'sequence': self._next_prelabel_line_sequence(),
            })
            self.write({
                'lot_barcode': False,
                'kc_focus_token': self._bump_scan_focus(),
            })
            return self._reopen_self_action()
        except UserError as err:
            msg = err.args[0] if err.args else str(err)
            return self._error_return(msg)

    def action_confirm(self):
        self.ensure_one()
        wo = self.workorder_id
        lines = self.line_ids
        raw_one = self._lot_barcode_scan_raw()
        if not lines and raw_one:
            try:
                lot = self._lookup_lot_from_scan(raw_one)
                self._bind_workorder_from_lot(lot)
                self.env['mrp.supervisor.consume.prelabel.line.wizard'].create({
                    'wizard_id': self.id,
                    'lot_id': lot.id,
                    'sequence': self._next_prelabel_line_sequence(),
                })
                self.lot_barcode = False
                lines = self.line_ids
                wo = self.workorder_id
            except UserError as err:
                msg = err.args[0] if err.args else str(err)
                return self._error_return(msg)
        if not lines:
            return self._error_return(
                _('Añada al menos una pre-etiqueta: use «Añadir a la lista» por cada escaneo, '
                  'o deje un solo código en el campo y pulse «Confirmar y producir».')
            )
        if not wo or not wo.exists():
            return self._error_return(_('Escanee al menos una pre-etiqueta para identificar la orden de trabajo.'))
        if wo.state != 'progress':
            return self._error_return(_('Inicie la orden de trabajo antes de confirmar la producción.'))
        if len(lines) != len(lines.mapped('lot_id')):
            return self._error_return(_('Hay lotes duplicados en la lista.'))

        lots = lines.mapped('lot_id')
        for lot in lots:
            if lot.kc_prelabel_state != 'pending':
                return self._error_return(
                    _('La pre-etiqueta «%s» ya no está pendiente.') % lot.name
                )
        try:
            wo.kc_consume_prelabel_lots(lots, employee=self.employee_id)
        except UserError as err:
            msg = err.args[0] if err.args else str(err)
            return self._error_return(msg)

        mo = wo.production_id
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Producción registrada'),
                'message': _(
                    'Se registraron %(count)s pre-etiqueta(s) en la orden %(mo)s / OT %(wo)s.'
                ) % {
                    'count': len(lots),
                    'mo': mo.name,
                    'wo': wo.display_name,
                },
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
