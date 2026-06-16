# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class MrpTabletConsumePrelabelLineWizard(models.TransientModel):
    _name = 'mrp.tablet.consume.prelabel.line.wizard'
    _description = 'Línea de pre-etiqueta escaneada (tablet)'
    _order = 'sequence desc, id desc'

    wizard_id = fields.Many2one(
        'mrp.tablet.consume.prelabel.lot.wizard',
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


class MrpTabletConsumePrelabelLotWizard(models.TransientModel):
    _name = 'mrp.tablet.consume.prelabel.lot.wizard'
    _description = 'Escanear pre-etiqueta y registrar producción (tablet)'

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
    lot_barcode = fields.Char(
        string='Código de lote',
        help='Escanee o pegue el código; pulse «Añadir a la lista». Puede acumular varias pre-etiquetas antes de confirmar.',
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
        help='Técnico: incrementa tras cada escaneo para devolver el foco al campo de código.',
    )
    line_ids = fields.One2many(
        'mrp.tablet.consume.prelabel.line.wizard',
        'wizard_id',
        string='Pre-etiquetas a producir',
    )

    def _tablet_reopen_self_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'name': _('Escanear pre-etiqueta'),
            'context': dict(self.env.context),
        }

    def _bump_scan_focus(self):
        self.ensure_one()
        return (self.kc_focus_token or 0) + 1

    def _next_prelabel_line_sequence(self):
        self.ensure_one()
        if not self.line_ids:
            return 1
        return max(self.line_ids.mapped('sequence')) + 1

    def _tablet_consume_prelabel_error_return(self, message, title=None):
        """Vacía el código escaneado, muestra el error y vuelve a abrir el asistente (foco en campo con default_focus)."""
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
                'next': self._tablet_reopen_self_action(),
            },
        }

    def _lot_barcode_scan_raw(self):
        """Código escaneado: campo guardado o contexto (Enter/handheld antes del save)."""
        self.ensure_one()
        raw = (self.lot_barcode or '').strip()
        if not raw:
            raw = (self.env.context.get('kc_lot_barcode_scan') or '').strip()
        return raw

    def _lookup_pending_prelabel_lot(self, raw):
        """Localiza un `stock.lot` pendiente de esta MO a partir del escaneo (nombre exacto o GS1)."""
        self.ensure_one()
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        mo = wo.production_id
        return self.env['stock.lot'].kc_find_pending_prelabel_from_scan(
            raw,
            mo=mo,
            company=mo.company_id,
        )

    def action_add_scan(self):
        """Añade la pre-etiqueta del campo de escaneo a la tabla (sin producir aún)."""
        self.ensure_one()
        try:
            wo = self.workorder_id
            if not wo.exists():
                raise UserError(_('La orden de trabajo ya no existe.'))
            if wo.state != 'progress':
                raise UserError(_('Inicie la orden de trabajo antes de escanear la pre-etiqueta.'))
            raw = self._lot_barcode_scan_raw()
            if not raw:
                raise UserError(_('Escanee o pegue el código antes de añadir a la lista.'))
            lot = self._lookup_pending_prelabel_lot(raw)
            if self.line_ids.filtered(lambda l: l.lot_id == lot):
                raise UserError(_('El lote «%s» ya está en la lista.') % lot.name)
            self.env['mrp.tablet.consume.prelabel.line.wizard'].create({
                'wizard_id': self.id,
                'lot_id': lot.id,
                'sequence': self._next_prelabel_line_sequence(),
            })
            self.write({
                'lot_barcode': False,
                'kc_focus_token': self._bump_scan_focus(),
            })
            return self._tablet_reopen_self_action()
        except UserError as err:
            msg = err.args[0] if err.args else str(err)
            return self._tablet_consume_prelabel_error_return(msg)

    def action_confirm(self):
        """Produce todas las líneas; consumo MP vía ``workorder.kc_consume_prelabel_lots`` → ``_tablet_create_batch_lot_impl``."""
        self.ensure_one()
        wo = self.workorder_id
        if not wo.exists():
            raise UserError(_('La orden de trabajo ya no existe.'))
        action, _eid, employee, workcenter = wo._tablet_validate_session()
        if action:
            return wo._tablet_return_with_refreshed_pin(action)
        if wo.state != 'progress':
            raise UserError(_('Inicie la orden de trabajo antes de escanear la pre-etiqueta.'))

        lines = self.line_ids
        raw_one = self._lot_barcode_scan_raw()
        if not lines and raw_one:
            try:
                lot = self._lookup_pending_prelabel_lot(raw_one)
                self.env['mrp.tablet.consume.prelabel.line.wizard'].create({
                    'wizard_id': self.id,
                    'lot_id': lot.id,
                    'sequence': self._next_prelabel_line_sequence(),
                })
                self.lot_barcode = False
                lines = self.line_ids
            except UserError as err:
                msg = err.args[0] if err.args else str(err)
                return self._tablet_consume_prelabel_error_return(msg)
        if not lines:
            return self._tablet_consume_prelabel_error_return(
                _('Añada al menos una pre-etiqueta: use «Añadir a la lista» por cada escaneo, '
                  'o deje un solo código en el campo y pulse «Confirmar y producir» (una sola pre-etiqueta).')
            )
        if len(lines) != len(lines.mapped('lot_id')):
            return self._tablet_consume_prelabel_error_return(_('Hay lotes duplicados en la lista.'))

        lots = lines.sorted(key=lambda r: (r.sequence, r.id)).mapped('lot_id')
        try:
            return wo.kc_consume_prelabel_lots(lots, employee=employee)
        except UserError as err:
            msg = err.args[0] if err.args else str(err)
            return self._tablet_consume_prelabel_error_return(msg)
