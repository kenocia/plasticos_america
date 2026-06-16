# -*- coding: utf-8 -*-

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class KcPhysicalLotScanSession(models.Model):
    _name = 'kc.physical.lot.scan.session'
    _description = 'Sesión de levantamiento físico previo por lote'
    _inherit = ['kc.gs1.barcode.mixin']
    _order = 'created_date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'kc.physical.lot.scan.session'
        ) or '/',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        required=True,
    )
    location_default_id = fields.Many2one(
        'stock.location',
        string='Ubicación física por defecto',
        domain="[('id', 'in', kc_physical_allowed_location_ids)]",
    )
    state = fields.Selection(
        [
            ('draft', 'En curso'),
            ('done', 'Cerrada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        required=True,
    )
    line_ids = fields.One2many(
        'kc.physical.lot.scan.line',
        'session_id',
        string='Lotes escaneados',
    )
    line_count = fields.Integer(
        string='Lotes',
        compute='_compute_line_count',
    )
    created_date = fields.Datetime(
        string='Fecha de inicio',
        default=fields.Datetime.now,
        required=True,
    )
    closed_date = fields.Datetime(
        string='Fecha de cierre',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    kc_physical_auto_location = fields.Boolean(
        string='Ubicación automática',
        compute='_compute_kc_physical_location_flags',
    )
    kc_physical_require_location = fields.Boolean(
        string='Requiere elegir ubicación',
        compute='_compute_kc_physical_location_flags',
    )
    active_ramp_index = fields.Integer(
        string='Rampla activa',
        default=1,
        copy=False,
        help='Índice de la rampla en curso dentro de esta sesión.',
    )
    active_scan_session_uid = fields.Char(
        string='UID rampla activa',
        copy=False,
        help='Identificador técnico de la rampla en curso.',
    )
    line_ready_count = fields.Integer(
        string='Listos para entrada',
        compute='_compute_line_stock_stats',
        help='Lotes sin existencia en la ubicación reportada (aptos para ajuste de entrada).',
    )
    line_with_stock_count = fields.Integer(
        string='Con stock en ubic. reportada',
        compute='_compute_line_stock_stats',
        help='Lotes que aún tienen existencia en Odoo en la ubicación reportada.',
    )
    odoo_last_refresh_date = fields.Datetime(
        string='Última act. Odoo',
        readonly=True,
    )
    adjustment_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán de ajuste',
        copy=False,
        readonly=True,
    )
    adjustment_state = fields.Selection(
        [
            ('none', 'Sin ajuste'),
            ('applied', 'Ajuste aplicado'),
        ],
        string='Estado ajuste',
        default='none',
        required=True,
        copy=False,
    )
    adjustment_date = fields.Datetime(
        string='Fecha ajuste',
        readonly=True,
    )
    adjustment_picking_state = fields.Selection(
        related='adjustment_picking_id.state',
        string='Estado albarán ajuste',
    )
    return_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán de devolución',
        copy=False,
        readonly=True,
    )
    return_state = fields.Selection(
        [
            ('none', 'Sin devolución'),
            ('applied', 'Devolución aplicada'),
        ],
        string='Estado devolución',
        default='none',
        required=True,
        copy=False,
    )
    return_date = fields.Datetime(
        string='Fecha devolución',
        readonly=True,
    )
    return_picking_state = fields.Selection(
        related='return_picking_id.state',
        string='Estado albarán devolución',
    )

    @api.depends('line_ids', 'line_ids.has_stock_at_reported')
    def _compute_line_stock_stats(self):
        for session in self:
            lines = session.line_ids
            session.line_with_stock_count = len(
                lines.filtered('has_stock_at_reported')
            )
            session.line_ready_count = len(lines) - session.line_with_stock_count

    @api.depends('line_ids')
    def _compute_line_count(self):
        for session in self:
            session.line_count = len(session.line_ids)

    @api.depends('company_id', 'company_id.kc_physical_scan_location_ids')
    def _compute_kc_physical_location_flags(self):
        for session in self:
            extra_locs = session.company_id.kc_physical_scan_location_ids
            session.kc_physical_auto_location = len(extra_locs) == 1
            session.kc_physical_require_location = len(extra_locs) > 1

    def _kc_physical_scan_company(self):
        self.ensure_one()
        return self.company_id

    @api.depends('company_id', 'company_id.kc_physical_scan_location_ids')
    def _compute_kc_physical_allowed_location_ids(self):
        return super()._compute_kc_physical_allowed_location_ids()

    @api.model
    def _kc_physical_default_location_for_company(self, company):
        extra_locs = company.kc_physical_scan_location_ids
        if len(extra_locs) == 1:
            return extra_locs
        return self.env['stock.location']

    def _kc_physical_default_reported_location(self):
        self.ensure_one()
        if self.location_default_id:
            return self.location_default_id
        return self._kc_physical_default_location_for_company(self.company_id)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = seq.next_by_code('kc.physical.lot.scan.session') or '/'
            if not vals.get('location_default_id'):
                company = self.env['res.company'].browse(
                    vals.get('company_id') or self.env.company.id
                )
                default_loc = self._kc_physical_default_location_for_company(company)
                if default_loc:
                    vals['location_default_id'] = default_loc.id
        return super().create(vals_list)

    def _kc_physical_init_active_ramp(self):
        """Asegura UID e índice de rampla activa al abrir el escaneo."""
        self.ensure_one()
        if self.active_scan_session_uid:
            if not self.active_ramp_index:
                self.active_ramp_index = 1
            return
        Line = self.env['kc.physical.lot.scan.line']
        last_line = Line.search(
            [('session_id', '=', self.id)],
            order='ramp_index desc, session_line_no desc, id desc',
            limit=1,
        )
        if last_line and last_line.scan_session_uid:
            self.write({
                'active_scan_session_uid': last_line.scan_session_uid,
                'active_ramp_index': last_line.ramp_index or 1,
            })
        else:
            self.write({
                'active_scan_session_uid': str(uuid.uuid4()),
                'active_ramp_index': 1,
            })

    def action_open_scan_wizard(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede escanear en sesiones en curso.'))
        location = self._kc_physical_default_reported_location()
        if not location:
            raise UserError(
                _('Indique la ubicación física por defecto en la sesión antes de escanear.')
            )
        self._kc_physical_init_active_ramp()
        wizard = self.env['kc.physical.lot.scan.wizard'].create({
            'session_id': self.id,
            'location_reported_id': location.id,
            'ramp_index': self.active_ramp_index,
            'scan_session_uid': self.active_scan_session_uid,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escanear GS1 — %s') % self.name,
            'res_model': 'kc.physical.lot.scan.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_start_scan(self):
        """Crea una sesión en curso y abre el wizard de escaneo."""
        draft = self.filtered(lambda s: s.state == 'draft')[:1]
        if draft:
            return draft.action_open_scan_wizard()
        session = self.env['kc.physical.lot.scan.session'].create({})
        return session.action_open_scan_wizard()

    def action_close_session(self):
        for session in self:
            if session.state != 'draft':
                continue
            session.write({
                'state': 'done',
                'closed_date': fields.Datetime.now(),
            })

    def action_refresh_odoo_quantities(self):
        """Relee existencia Odoo en la ubicación reportada de cada línea (no modifica QR)."""
        for session in self:
            if not session.line_ids:
                raise UserError(_('No hay lotes escaneados en esta sesión.'))
            session.line_ids.action_refresh_odoo_quantities()
            session.odoo_last_refresh_date = fields.Datetime.now()
        if len(self) == 1:
            session = self
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Existencia Odoo actualizada'),
                    'message': _(
                        '%(ready)s lote(s) sin stock en ubicación reportada (listos para entrada). '
                        '%(blocked)s lote(s) aún con stock en esa ubicación.'
                    ) % {
                        'ready': session.line_ready_count,
                        'blocked': session.line_with_stock_count,
                    },
                    'type': 'success' if not session.line_with_stock_count else 'warning',
                    'sticky': bool(session.line_with_stock_count),
                },
            }
        return True

    def _kc_physical_get_adjustment_picking_type(self):
        self.ensure_one()
        picking_type = self.company_id.kc_physical_scan_adjustment_picking_type_id
        if not picking_type:
            raise UserError(
                _('Configure el tipo de operación de ajuste de entrada en '
                  'Ajustes → Compañías → Inventario físico previo.')
            )
        if picking_type.company_id and picking_type.company_id != self.company_id:
            raise UserError(
                _('El tipo de operación de ajuste no pertenece a la compañía de la sesión.')
            )
        if not picking_type.default_location_src_id:
            raise UserError(
                _('El tipo de operación %(type)s no tiene ubicación origen por defecto.')
                % {'type': picking_type.display_name}
            )
        return picking_type

    def _kc_physical_get_return_picking_type(self):
        self.ensure_one()
        picking_type = self.company_id.kc_physical_scan_return_picking_type_id
        if not picking_type:
            raise UserError(
                _('Configure el tipo de operación de devolución en '
                  'Ajustes → Compañías → Inventario físico previo.')
            )
        if picking_type.company_id and picking_type.company_id != self.company_id:
            raise UserError(
                _('El tipo de operación de devolución no pertenece a la compañía de la sesión.')
            )
        if not picking_type.default_location_dest_id:
            raise UserError(
                _('El tipo de operación %(type)s no tiene ubicación destino por defecto.')
                % {'type': picking_type.display_name}
            )
        return picking_type

    def _kc_physical_validate_zero_qr_lines(self):
        self.ensure_one()
        zero_qr = self.line_ids.filtered(
            lambda line: float_is_zero(
                line.qty_gs1 or 0.0,
                precision_rounding=line.product_uom_id.rounding,
            )
        )
        if zero_qr:
            names = ', '.join(zero_qr.mapped('lot_id.display_name')[:10])
            raise UserError(
                _('Hay lote(s) con cantidad QR en cero: %(lots)s')
                % {'lots': names}
            )

    def _kc_physical_validate_for_adjustment(self):
        self.ensure_one()
        if self.adjustment_picking_id and self.adjustment_picking_id.state != 'cancel':
            raise UserError(
                _('Ya existe un ajuste aplicado: %(pick)s.')
                % {'pick': self.adjustment_picking_id.display_name}
            )
        if self.return_picking_id and self.return_picking_id.state != 'cancel':
            raise UserError(
                _('Existe una devolución aplicada (%(pick)s). '
                  'Cancele la devolución antes de un nuevo ajuste de entrada.')
                % {'pick': self.return_picking_id.display_name}
            )
        if not self.line_ids:
            raise UserError(_('No hay lotes escaneados en esta sesión.'))

        self.line_ids.action_refresh_odoo_quantities()
        self.odoo_last_refresh_date = fields.Datetime.now()

        blocked = self.line_ids.filtered('has_stock_at_reported')
        if blocked:
            names = ', '.join(blocked.mapped('lot_id.display_name')[:10])
            extra = len(blocked) - 10
            suffix = _(' (y %(n)s más)') % {'n': extra} if extra > 0 else ''
            raise UserError(
                _('No se puede aplicar el ajuste: %(count)s lote(s) aún tienen '
                  'existencia en la ubicación reportada. Debe zerar inventario '
                  'en esas ubicaciones antes de continuar.\n%(lots)s%(suffix)s')
                % {'count': len(blocked), 'lots': names, 'suffix': suffix}
            )

        self._kc_physical_validate_zero_qr_lines()

    def _kc_physical_validate_for_return(self):
        self.ensure_one()
        if not self.adjustment_picking_id or self.adjustment_picking_id.state != 'done':
            raise UserError(
                _('Debe aplicar y validar primero el ajuste de entrada '
                  '(%(pick)s) antes de la devolución.')
                % {
                    'pick': self.adjustment_picking_id.display_name
                    if self.adjustment_picking_id else _('(sin albarán)'),
                }
            )
        if self.return_picking_id and self.return_picking_id.state != 'cancel':
            raise UserError(
                _('Ya existe una devolución aplicada: %(pick)s.')
                % {'pick': self.return_picking_id.display_name}
            )
        if not self.line_ids:
            raise UserError(_('No hay lotes escaneados en esta sesión.'))

        self.line_ids.action_refresh_odoo_quantities()
        self.odoo_last_refresh_date = fields.Datetime.now()

        insufficient = self.env['kc.physical.lot.scan.line']
        for line in self.line_ids:
            rounding = line.product_uom_id.rounding
            if float_compare(
                line.qty_physical or 0.0,
                line.qty_gs1 or 0.0,
                precision_rounding=rounding,
            ) < 0:
                insufficient |= line
        if insufficient:
            names = ', '.join(insufficient.mapped('lot_id.display_name')[:10])
            extra = len(insufficient) - 10
            suffix = _(' (y %(n)s más)') % {'n': extra} if extra > 0 else ''
            raise UserError(
                _('No se puede aplicar la devolución: %(count)s lote(s) no tienen '
                  'existencia suficiente en la ubicación reportada '
                  '(requerido = cantidad QR).\n%(lots)s%(suffix)s')
                % {'count': len(insufficient), 'lots': names, 'suffix': suffix}
            )

        self._kc_physical_validate_zero_qr_lines()

    def _kc_physical_create_adjustment_picking(self):
        self.ensure_one()
        picking_type = self._kc_physical_get_adjustment_picking_type()
        location_src = picking_type.default_location_src_id
        location_dest_default = picking_type.default_location_dest_id
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']

        picking = Picking.create({
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest_default.id if location_dest_default else False,
            'origin': self.name,
            'company_id': self.company_id.id,
            'note': _('Ajuste de entrada — inventario físico previo %s') % self.name,
        })

        for line in self.line_ids.sorted('session_line_no'):
            dest = line.location_reported_id
            qty = line.qty_gs1
            move = Move.create({
                'name': line.lot_id.display_name,
                'description_picking': _('Físico previo %s — lote %s') % (
                    self.name, line.lot_id.display_name,
                ),
                'product_id': line.product_id.id,
                'product_uom_qty': qty,
                'product_uom': line.product_uom_id.id,
                'picking_id': picking.id,
                'location_id': location_src.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
            })
            line.adjustment_move_id = move.id

            if line.product_id.tracking != 'none':
                MoveLine.create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'location_id': location_src.id,
                    'location_dest_id': dest.id,
                    'lot_id': line.lot_id.id,
                    'quantity': qty,
                    'picked': True,
                })
            move.write({'quantity': qty, 'picked': True})

        picking.action_confirm()
        picking.with_context(cancel_backorder=True)._action_done()
        return picking

    def _kc_physical_create_return_picking(self):
        self.ensure_one()
        picking_type = self._kc_physical_get_return_picking_type()
        location_dest = picking_type.default_location_dest_id
        location_src_default = picking_type.default_location_src_id
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']

        picking = Picking.create({
            'picking_type_id': picking_type.id,
            'location_id': location_src_default.id if location_src_default else False,
            'location_dest_id': location_dest.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'note': _('Devolución — inventario físico previo %s') % self.name,
        })

        for line in self.line_ids.sorted('session_line_no'):
            src = line.location_reported_id
            qty = line.qty_gs1
            move = Move.create({
                'name': line.lot_id.display_name,
                'description_picking': _('Devolución %s — lote %s') % (
                    self.name, line.lot_id.display_name,
                ),
                'product_id': line.product_id.id,
                'product_uom_qty': qty,
                'product_uom': line.product_uom_id.id,
                'picking_id': picking.id,
                'location_id': src.id,
                'location_dest_id': location_dest.id,
                'company_id': self.company_id.id,
            })
            line.return_move_id = move.id

            if line.product_id.tracking != 'none':
                MoveLine.create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'location_id': src.id,
                    'location_dest_id': location_dest.id,
                    'lot_id': line.lot_id.id,
                    'quantity': qty,
                    'picked': True,
                })
            move.write({'quantity': qty, 'picked': True})

        picking.action_confirm()
        picking.with_context(cancel_backorder=True)._action_done()
        return picking

    def action_apply_session_adjustment(self):
        """Genera un único albarán de entrada con todas las líneas de la sesión."""
        for session in self:
            session._kc_physical_validate_for_adjustment()
            picking = session._kc_physical_create_adjustment_picking()
            session.write({
                'adjustment_picking_id': picking.id,
                'adjustment_state': 'applied',
                'adjustment_date': fields.Datetime.now(),
            })
        if len(self) == 1:
            session = self
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ajuste de entrada aplicado'),
                    'message': _('Albarán %(pick)s validado con %(n)s lote(s).') % {
                        'pick': session.adjustment_picking_id.display_name,
                        'n': len(session.line_ids),
                    },
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'stock.picking',
                        'res_id': session.adjustment_picking_id.id,
                        'views': [[False, 'form']],
                        'target': 'current',
                    },
                },
            }
        return True

    def action_apply_session_return(self):
        """Genera un único albarán de devolución que revierte el ajuste de entrada."""
        for session in self:
            session._kc_physical_validate_for_return()
            picking = session._kc_physical_create_return_picking()
            session.write({
                'return_picking_id': picking.id,
                'return_state': 'applied',
                'return_date': fields.Datetime.now(),
            })
        if len(self) == 1:
            session = self
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Devolución aplicada'),
                    'message': _(
                        'Albarán %(pick)s validado. Se retiró el stock de '
                        '%(n)s lote(s) en sus ubicaciones reportadas.'
                    ) % {
                        'pick': session.return_picking_id.display_name,
                        'n': len(session.line_ids),
                    },
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'stock.picking',
                        'res_id': session.return_picking_id.id,
                        'views': [[False, 'form']],
                        'target': 'current',
                    },
                },
            }
        return True

    def action_open_adjustment_picking(self):
        self.ensure_one()
        if not self.adjustment_picking_id:
            raise UserError(_('Esta sesión no tiene albarán de ajuste.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Albarán de ajuste'),
            'res_model': 'stock.picking',
            'res_id': self.adjustment_picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_return_picking(self):
        self.ensure_one()
        if not self.return_picking_id:
            raise UserError(_('Esta sesión no tiene albarán de devolución.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Albarán de devolución'),
            'res_model': 'stock.picking',
            'res_id': self.return_picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reopen_session(self):
        self.filtered(lambda s: s.state == 'done').write({
            'state': 'draft',
            'closed_date': False,
        })
