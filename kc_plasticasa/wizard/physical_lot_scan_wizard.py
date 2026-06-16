# -*- coding: utf-8 -*-

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class KcPhysicalLotScanWizard(models.TransientModel):
    _name = 'kc.physical.lot.scan.wizard'
    _description = 'Wizard de escaneo GS1 — inventario físico previo'
    _inherit = ['kc.gs1.barcode.mixin']

    session_id = fields.Many2one(
        'kc.physical.lot.scan.session',
        string='Sesión',
        required=True,
        readonly=True,
    )
    barcode_input = fields.Char(
        string='Escanear QR GS1',
    )
    location_reported_id = fields.Many2one(
        'stock.location',
        string='Ubicación física',
        domain="[('id', 'in', kc_physical_allowed_location_ids)]",
    )
    message = fields.Text(
        string='Mensaje',
        readonly=True,
    )
    state = fields.Selection(
        [
            ('scan', 'Escanear'),
            ('error', 'Error'),
        ],
        string='Estado',
        default='scan',
        readonly=True,
    )
    line_ids = fields.Many2many(
        'kc.physical.lot.scan.line',
        compute='_compute_line_ids',
        string='Lotes en rampla',
        readonly=True,
    )
    ramp_line_count = fields.Integer(
        string='Lotes en rampla',
        compute='_compute_line_ids',
    )
    scan_session_uid = fields.Char(
        string='Rampla actual',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
    )
    ramp_index = fields.Integer(
        string='Número de rampla',
        default=1,
        readonly=True,
    )
    next_line_no = fields.Integer(
        string='Próximo #',
        compute='_compute_next_line_no',
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
    )
    kc_scan_refresh = fields.Integer(default=0)
    kc_physical_auto_location = fields.Boolean(
        related='session_id.kc_physical_auto_location',
    )
    kc_physical_require_location = fields.Boolean(
        related='session_id.kc_physical_require_location',
    )

    @api.depends('session_id', 'scan_session_uid', 'kc_scan_refresh')
    def _compute_line_ids(self):
        Line = self.env['kc.physical.lot.scan.line']
        for wizard in self:
            if wizard.session_id and wizard.scan_session_uid:
                wizard.line_ids = Line.search(
                    [
                        ('session_id', '=', wizard.session_id.id),
                        ('scan_session_uid', '=', wizard.scan_session_uid),
                    ],
                    order='session_line_no desc, scan_date desc, id desc',
                )
            else:
                wizard.line_ids = Line
            wizard.ramp_line_count = len(wizard.line_ids)

    @api.depends('session_id', 'scan_session_uid', 'ramp_index', 'kc_scan_refresh')
    def _compute_next_line_no(self):
        Line = self.env['kc.physical.lot.scan.line']
        for wizard in self:
            if wizard.session_id and wizard.scan_session_uid:
                wizard.next_line_no = Line._next_session_line_no(
                    wizard.ramp_index,
                    wizard.scan_session_uid,
                    wizard.session_id.id,
                )
            else:
                wizard.next_line_no = 1

    def _kc_physical_sync_session_ramp(self):
        self.ensure_one()
        if self.session_id:
            self.session_id.write({
                'active_ramp_index': self.ramp_index,
                'active_scan_session_uid': self.scan_session_uid,
            })

    def _kc_physical_scan_company(self):
        self.ensure_one()
        if self.session_id:
            return self.session_id.company_id
        session = self.env['kc.physical.lot.scan.session'].browse(
            self.env.context.get('default_session_id')
        )
        return session.company_id if session else self.env.company

    @api.depends('session_id', 'session_id.company_id')
    def _compute_kc_physical_allowed_location_ids(self):
        return super()._compute_kc_physical_allowed_location_ids()

    @api.model
    def _default_session_from_context(self):
        session = self.env['kc.physical.lot.scan.session'].browse(
            self.env.context.get('default_session_id')
        )
        if not session and self.env.context.get('active_model') == 'kc.physical.lot.scan.session':
            session = self.env['kc.physical.lot.scan.session'].browse(
                self.env.context.get('active_id')
            )
        return session

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        session = self._default_session_from_context()
        if session and 'location_reported_id' in fields_list:
            location = session._kc_physical_default_reported_location()
            if location:
                res.setdefault('location_reported_id', location.id)
        return res

    @api.onchange('location_reported_id')
    def _onchange_location_reported_id(self):
        if self.location_reported_id and self.session_id and not self.session_id.location_default_id:
            self.session_id.location_default_id = self.location_reported_id

    def _reopen_wizard_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escanear GS1 — %s') % self.session_id.name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': dict(self.env.context),
        }

    def _sync_barcode_from_context(self):
        self.ensure_one()
        raw = (self.barcode_input or '').strip()
        if not raw:
            raw = (self.env.context.get('kc_gs1_barcode_scan') or '').strip()
        if raw and raw != (self.barcode_input or '').strip():
            self.barcode_input = raw
        return raw

    def _set_scan_error(self, message):
        self.write({
            'message': message,
            'state': 'error',
            'barcode_input': False,
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
            'kc_scan_refresh': (self.kc_scan_refresh or 0) + 1,
        })

    def _set_scan_success(self, message):
        vals = {
            'message': message,
            'state': 'scan',
            'barcode_input': False,
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
            'kc_scan_refresh': (self.kc_scan_refresh or 0) + 1,
        }
        if self.location_reported_id and self.session_id and not self.session_id.location_default_id:
            self.session_id.location_default_id = self.location_reported_id
        self.write(vals)

    def _validate_session(self):
        self.ensure_one()
        if self.session_id.state != 'draft':
            raise UserError(_('La sesión no está en curso.'))
        if not self.location_reported_id:
            raise UserError(_('Indique la ubicación física antes de escanear.'))

    def _process_scan(self):
        self.ensure_one()
        session = self.session_id
        barcode = self._sync_barcode_from_context()
        if not barcode:
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )

        parsed = self.parse_gs1_barcode(barcode)
        product = self.kc_gs1_find_product(parsed['product_code'])
        if not product:
            raise UserError(
                _('Producto no encontrado para el código GS1: %s') % parsed['product_code']
            )

        lot = self.kc_gs1_find_lot(product, parsed['lot_name'], session.company_id)
        if not lot:
            raise UserError(
                _('El lote %(lot)s no existe para el producto %(product)s.')
                % {'lot': parsed['lot_name'], 'product': product.display_name}
            )
        if lot.product_id != product:
            raise UserError(
                _('El lote %(lot)s pertenece a %(lot_product)s, no a %(product)s.')
                % {
                    'lot': lot.display_name,
                    'lot_product': lot.product_id.display_name,
                    'product': product.display_name,
                }
            )

        Line = self.env['kc.physical.lot.scan.line']
        if Line.search_count([('session_id', '=', session.id), ('lot_id', '=', lot.id)]):
            raise UserError(
                _('El lote %s ya fue escaneado en esta sesión.') % lot.display_name
            )

        vals = Line._prepare_from_gs1_scan(
            session,
            product,
            lot,
            parsed,
            barcode,
            self.location_reported_id,
            scan_session_uid=self.scan_session_uid,
            ramp_index=self.ramp_index,
        )
        line = Line.create(vals)
        self._kc_physical_sync_session_ramp()

        mismatch = ''
        if line.location_mismatch:
            mismatch = _(
                '\nAviso: ubicación reportada (%(rep)s) difiere de la principal en sistema (%(sys)s).'
            ) % {
                'rep': line.location_reported_id.display_name,
                'sys': line.location_system_id.display_name if line.location_system_id else _('(sin stock)'),
            }

        movement_note = ''
        if line.last_movement_id:
            movement_note = _('\nÚltimo mov.: %(pick)s (%(date)s).') % {
                'pick': line.last_movement_id.display_name,
                'date': line.last_movement_date or '',
            }

        return _(
            'Lote %(lot)s registrado (#%(num)s).\n'
            'Odoo en %(loc)s: %(phys)s %(uom)s\n'
            'Cantidad QR: %(qr)s %(uom)s%(movement)s%(mismatch)s'
        ) % {
            'lot': lot.display_name,
            'num': line.session_line_no,
            'loc': line.location_reported_id.display_name,
            'qr': line.qty_gs1,
            'phys': line.qty_physical,
            'uom': product.uom_id.name,
            'movement': movement_note,
            'mismatch': mismatch,
        }

    def action_process_qr(self):
        self.ensure_one()
        try:
            self._validate_session()
            msg = self._process_scan()
            self._set_scan_success(msg)
        except (UserError, ValidationError) as err:
            self._set_scan_error(err.args[0] if err.args else str(err))
        return self._reopen_wizard_action()

    def action_on_barcode_scanned(self):
        self.ensure_one()
        if not self._sync_barcode_from_context():
            return self._reopen_wizard_action()
        return self.action_process_qr()

    def action_new_ramp(self):
        """Inicia una nueva rampla: conserva lo escaneado y reinicia el listado."""
        self.ensure_one()
        Line = self.env['kc.physical.lot.scan.line']
        new_ramp_index = (self.ramp_index or 1) + 1
        new_uid = str(uuid.uuid4())
        next_no = Line._next_session_line_no(
            new_ramp_index, new_uid, self.session_id.id,
        )
        message = _(
            'Rampla %(ramp)s iniciada. Próximo número: #%(next)s.'
        ) % {'ramp': new_ramp_index, 'next': next_no}
        vals = {
            'ramp_index': new_ramp_index,
            'scan_session_uid': new_uid,
            'barcode_input': False,
            'state': 'scan',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
            'kc_scan_refresh': (self.kc_scan_refresh or 0) + 1,
            'message': message,
        }
        if self.kc_physical_require_location:
            vals['location_reported_id'] = False
            message = _(
                'Rampla %(ramp)s. Indique la ubicación. Próximo número: #%(next)s.'
            ) % {'ramp': new_ramp_index, 'next': next_no}
            vals['message'] = message
        else:
            location = self.session_id._kc_physical_default_reported_location()
            if location:
                vals['location_reported_id'] = location.id
        self.write(vals)
        self._kc_physical_sync_session_ramp()
        return self._reopen_wizard_action()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
