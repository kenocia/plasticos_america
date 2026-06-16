# -*- coding: utf-8 -*-

import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

GS1_SEPARATOR = '\x1d'
_GS1_SEPARATORS = (
    '\x1d', '\x1D', '\u001d', '\u001D',
    '\x1e', '\x1E',
    chr(29), chr(30),
    '<GS>', '<gs>',
    ']d2', ']C1',
)
_GS1_CONCATENATED_RE = re.compile(
    r'^240([\w./-]+?)10(.+?)30(\d+)$',
    re.IGNORECASE,
)


class KcInternalLotTransferWizard(models.TransientModel):
    _name = 'kc.internal.lot.transfer.wizard'
    _description = 'Wizard de transferencia interna por lotes GS1'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        default=lambda self: _('Operaciones internas'),
        required=True,
    )
    session_id = fields.Many2one(
        'kc.internal.lot.scan.session',
        string='Sesión',
        required=True,
        readonly=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo de operación interna',
        domain=lambda self: [
            ('code', '=', 'internal'),
            ('kc_enable_internal_lot_scanner', '=', True),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.env.company.id),
        ],
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
        readonly=True,
    )
    barcode_input = fields.Char(
        string='Escanear QR GS1',
    )
    line_ids = fields.One2many(
        related='session_id.line_ids',
        string='Lotes escaneados',
        readonly=False,
    )
    message = fields.Text(
        string='Resultado del escaneo',
        readonly=True,
    )
    scan_alert_type = fields.Selection(
        [
            ('info', 'Información'),
            ('success', 'Éxito'),
            ('warning', 'Advertencia'),
            ('danger', 'Error'),
        ],
        string='Tipo de alerta',
        default='info',
        readonly=True,
    )
    scan_result_html = fields.Html(
        string='Resultado del escaneo',
        compute='_compute_scan_result_html',
        sanitize=False,
    )
    state = fields.Selection(
        [
            ('scan', 'Escanear'),
            ('done', 'Finalizado'),
        ],
        string='Estado',
        default='scan',
        readonly=True,
    )
    scan_count = fields.Integer(
        string='Lotes escaneados',
        compute='_compute_scan_count',
    )
    kc_focus_token = fields.Integer(
        string='Token de foco escaneo',
        default=0,
        help='Técnico: incrementa tras cada escaneo para devolver el foco al campo QR.',
    )
    kc_mark_low_quality = fields.Boolean(
        string='Baja calidad',
        compute='_compute_kc_mark_low_quality',
    )

    @api.depends('picking_type_id')
    def _compute_kc_mark_low_quality(self):
        picking_type_model = self.env['stock.picking.type']
        has_low_quality_flag = 'kc_mark_low_quality' in picking_type_model._fields
        for wizard in self:
            picking_type = wizard.picking_type_id
            wizard.kc_mark_low_quality = bool(
                has_low_quality_flag
                and picking_type
                and picking_type.kc_mark_low_quality
            )

    def _picking_type_marks_low_quality(self):
        self.ensure_one()
        picking_type = self.picking_type_id
        if not picking_type or 'kc_mark_low_quality' not in picking_type._fields:
            return False
        return bool(picking_type.kc_mark_low_quality)

    @api.depends('session_id.line_ids')
    def _compute_scan_count(self):
        for wizard in self:
            wizard.scan_count = len(wizard.session_id.line_ids)

    @api.depends('message', 'scan_alert_type')
    def _compute_scan_result_html(self):
        from markupsafe import escape
        for wizard in self:
            if not wizard.message:
                wizard.scan_result_html = (
                    '<div class="alert alert-info mb-0 py-2" role="status">'
                    'Escanee un QR GS1. Aquí verá si el lote se agregó o el motivo del error.'
                    '</div>'
                )
                continue
            css_map = {
                'success': 'success',
                'danger': 'danger',
                'warning': 'warning',
                'info': 'info',
            }
            css = css_map.get(wizard.scan_alert_type, 'info')
            icon = ''
            if css == 'danger':
                icon = '<i class="fa fa-exclamation-triangle me-2" title="Error"></i>'
            elif css == 'success':
                icon = '<i class="fa fa-check-circle me-2" title="Correcto"></i>'
            wizard.scan_result_html = (
                f'<div class="alert alert-{css} mb-0 py-3 fs-5 fw-bold" role="alert">'
                f'{icon}{escape(wizard.message)}'
                '</div>'
            )

    @api.model
    def _prepare_new_wizard_vals(self):
        session = self.env['kc.internal.lot.scan.session'].create({
            'company_id': self.env.company.id,
        })
        return {'session_id': session.id}

    @api.model
    def create_new(self):
        """Abre un wizard con sesión; el tipo de operación se elige en el formulario."""
        return self.create(self._prepare_new_wizard_vals())

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'session_id' in fields_list and not res.get('session_id'):
            res['session_id'] = self._prepare_new_wizard_vals()['session_id']
        return res

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        for wizard in self:
            if wizard.picking_type_id:
                wizard.name = wizard.picking_type_id.name
            wizard._apply_picking_type_locations()

    def write(self, vals):
        res = super().write(vals)
        if 'picking_type_id' in vals:
            for wizard in self:
                wizard._apply_picking_type_locations()
        return res

    def _apply_picking_type_locations(self):
        self.ensure_one()
        picking_type = self.picking_type_id
        if not picking_type:
            self.location_id = False
            self.location_dest_id = False
            return
        self._validate_picking_type(picking_type)
        self.location_id = picking_type.default_location_src_id
        self.location_dest_id = picking_type.default_location_dest_id
        if self.session_id:
            self.session_id.write({
                'picking_type_id': picking_type.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
            })

    def _validate_picking_type(self, picking_type):
        if not picking_type:
            raise UserError(_('Debe seleccionar un tipo de operación interna.'))
        if picking_type.code != 'internal':
            raise UserError(_('El tipo de operación seleccionado no es interno.'))
        if not picking_type.default_location_src_id:
            raise UserError(
                _('El tipo de operación seleccionado no tiene ubicación origen configurada.')
            )
        if not picking_type.default_location_dest_id:
            raise UserError(
                _('El tipo de operación seleccionado no tiene ubicación destino configurada.')
            )

    def _ensure_locations_configured(self):
        self.ensure_one()
        if not self.picking_type_id:
            raise UserError(_('Debe seleccionar un tipo de operación interna.'))
        self._validate_picking_type(self.picking_type_id)
        if not self.location_id or not self.location_dest_id:
            self._apply_picking_type_locations()

    @api.model
    def _normalize_gs1_raw(self, barcode):
        raw = str(barcode).strip()
        raw = raw.replace('\\x1d', GS1_SEPARATOR).replace('\\x1D', GS1_SEPARATOR)
        for sep in _GS1_SEPARATORS:
            if sep and sep != GS1_SEPARATOR:
                raw = raw.replace(sep, GS1_SEPARATOR)
        return raw

    @api.model
    def _parse_gs1_concatenated(self, raw):
        match = _GS1_CONCATENATED_RE.match(raw)
        if not match:
            return None
        product_code, lot_name, qty_str = match.group(1), match.group(2), match.group(3)
        if not product_code or not lot_name or not qty_str:
            return None
        return {
            'product_code': product_code,
            'lot_name': lot_name,
            'qty': float(qty_str),
        }

    @api.model
    def _parse_gs1_blocks(self, raw):
        blocks = [b.strip() for b in raw.split(GS1_SEPARATOR) if b.strip()]
        if not blocks:
            return None
        first = blocks[0]
        if not first.startswith('240'):
            return None
        product_code = first[3:]
        if not product_code:
            return None
        lot_name = None
        qty = 0.0
        for block in blocks[1:]:
            if block.startswith('10') and not lot_name:
                lot_name = block[2:]
            elif block.startswith('30') and float_is_zero(qty, precision_digits=6):
                qty_str = block[2:]
                if not qty_str.isdigit():
                    return None
                qty = float(qty_str)
        if not lot_name or float_is_zero(qty, precision_digits=6):
            return None
        return {
            'product_code': product_code,
            'lot_name': lot_name,
            'qty': qty,
        }

    @api.model
    def _parse_gs1_qr(self, barcode_raw):
        if not barcode_raw or not str(barcode_raw).strip():
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )
        raw = self._normalize_gs1_raw(barcode_raw)
        if not raw.startswith('240'):
            raise UserError(_('QR inválido. El primer bloque debe iniciar con 240.'))
        parsed = self._parse_gs1_blocks(raw)
        if not parsed:
            parsed = self._parse_gs1_concatenated(raw)
        if not parsed:
            compact = raw.replace(GS1_SEPARATOR, '')
            parsed = self._parse_gs1_concatenated(compact)
        if not parsed:
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )
        return parsed

    @api.model
    def _normalize_gs1_product_code(self, code):
        """Clave de comparación: sin espacios y en mayúsculas."""
        return re.sub(r'\s+', '', (code or '').strip()).upper()

    @api.model
    def _product_gs1_match_values(self, product):
        """Valores del producto/plantilla usados para cruzar con el QR."""
        template = product.product_tmpl_id
        values = [
            product.barcode,
            product.default_code,
            template.default_code,
        ]
        if 'kc_gs1_code' in product._fields:
            values.append(product.kc_gs1_code)
        if 'kc_gs1_code' in template._fields:
            values.append(template.kc_gs1_code)
        return values

    @api.model
    def _find_product_by_gs1_code(self, product_code):
        Product = self.env['product.product']
        domain_active = [('active', '=', True)]
        searches = [
            [('barcode', '=', product_code)],
            [('default_code', '=', product_code)],
            [('product_tmpl_id.default_code', '=', product_code)],
        ]
        if 'kc_gs1_code' in Product._fields:
            searches.insert(2, [('kc_gs1_code', '=', product_code)])
        if 'kc_gs1_code' in self.env['product.template']._fields:
            searches.append([('product_tmpl_id.kc_gs1_code', '=', product_code)])

        for extra_domain in searches:
            products = Product.search(domain_active + extra_domain)
            if len(products) > 1:
                raise UserError(
                    _('El código GS1 %(code)s coincide con múltiples productos. Corrija la configuración.')
                    % {'code': product_code}
                )
            if products:
                return products

        norm_code = self._normalize_gs1_product_code(product_code)
        if not norm_code:
            return Product

        prefix = product_code[: min(len(product_code), 12)]
        candidate_leaves = [
            ('default_code', 'ilike', prefix),
            ('barcode', 'ilike', prefix),
            ('product_tmpl_id.default_code', 'ilike', prefix),
        ]
        if 'kc_gs1_code' in Product._fields:
            candidate_leaves.insert(2, ('kc_gs1_code', 'ilike', prefix))
        if 'kc_gs1_code' in self.env['product.template']._fields:
            candidate_leaves.append(('product_tmpl_id.kc_gs1_code', 'ilike', prefix))
        candidate_domain = candidate_leaves[:1]
        for leaf in candidate_leaves[1:]:
            candidate_domain = ['|'] + candidate_domain + [leaf]
        candidates = Product.search(domain_active + candidate_domain)
        matches = Product
        for product in candidates:
            for value in self._product_gs1_match_values(product):
                if value and self._normalize_gs1_product_code(value) == norm_code:
                    matches |= product
                    break

        if len(matches) > 1:
            raise UserError(
                _('El código GS1 %(code)s coincide con múltiples productos. Corrija la configuración.')
                % {'code': product_code}
            )
        return matches[:1] if matches else Product

    def _find_lot(self, product, lot_name):
        self.ensure_one()
        company = self.session_id.company_id or self.env.company
        return self.env['stock.lot'].search([
            ('name', '=', lot_name),
            ('product_id', '=', product.id),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ], limit=1)

    def _get_available_qty_exact_location(self, product, lot, location, qty):
        """Disponibilidad exacta en ubicación (sin sububicaciones)."""
        self.ensure_one()
        Quant = self.env['stock.quant']
        company = self.session_id.company_id or self.env.company
        quants = Quant.search([
            ('product_id', '=', product.id),
            ('lot_id', '=', lot.id),
            ('location_id', '=', location.id),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ])
        rounding = product.uom_id.rounding
        available_qty = sum(q.quantity - q.reserved_quantity for q in quants)
        if float_compare(available_qty, qty, precision_rounding=rounding) >= 0:
            return available_qty

        other_quants = Quant.search([
            ('product_id', '=', product.id),
            ('lot_id', '=', lot.id),
            ('location_id', '!=', location.id),
            ('quantity', '>', 0),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company.id),
        ], limit=1)
        if other_quants and float_compare(available_qty, qty, precision_rounding=rounding) < 0:
            raise UserError(
                _('El lote %(lot)s existe, pero no está disponible en la ubicación origen %(loc)s.')
                % {'lot': lot.display_name, 'loc': location.display_name}
            )
        raise UserError(
            _('El lote %(lot)s no tiene disponibilidad suficiente en la ubicación %(loc)s. '
              'Disponible: %(avail)s, requerido: %(req)s.')
            % {
                'lot': lot.display_name,
                'loc': location.display_name,
                'avail': available_qty,
                'req': qty,
            }
        )

    def _is_duplicate_scan(self, lot, barcode_raw):
        self.ensure_one()
        session = self.session_id
        if session.line_ids.filtered(lambda l: l.lot_id == lot):
            return True
        if barcode_raw and session.line_ids.filtered(lambda l: l.barcode_raw == barcode_raw):
            return True
        return False

    def _reload_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transferencia interna GS1'),
            'res_model': 'kc.internal.lot.transfer.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_process_qr(self):
        self.ensure_one()
        try:
            return self._action_process_qr_impl()
        except (UserError, ValidationError) as error:
            msg = error.args[0] if error.args else _('Error al procesar el escaneo.')
            if isinstance(msg, dict):
                msg = msg.get('message') or str(msg)
            self.write({
                'barcode_input': False,
                'message': msg,
                'scan_alert_type': 'danger',
                'kc_focus_token': (self.kc_focus_token or 0) + 1,
            })
            return self._reload_wizard()

    def _action_process_qr_impl(self):
        self.ensure_one()
        self._ensure_locations_configured()
        if not self.barcode_input:
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )

        parsed = self._parse_gs1_qr(self.barcode_input)
        product = self._find_product_by_gs1_code(parsed['product_code'])
        if not product:
            raise UserError(
                _('Producto no encontrado para el código GS1: %s.') % parsed['product_code']
            )

        lot = self._find_lot(product, parsed['lot_name'])
        if not lot:
            raise UserError(
                _('El lote %(lot)s no existe para el producto %(product)s.')
                % {'lot': parsed['lot_name'], 'product': product.display_name}
            )

        qty = parsed['qty']
        if self._is_duplicate_scan(lot, self.barcode_input):
            raise UserError(_('Este lote ya fue escaneado en esta sesión.'))

        self._get_available_qty_exact_location(
            product, lot, self.location_id, qty
        )

        SessionLine = self.env['kc.internal.lot.scan.session.line']
        SessionLine.create({
            'session_id': self.session_id.id,
            'product_id': product.id,
            'lot_id': lot.id,
            'qty': qty,
            'product_uom_id': product.uom_id.id,
            'barcode_raw': self.barcode_input,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
        })

        self.env['kc.internal.lot.scan.log'].create({
            'session_name': self.session_id.name,
            'picking_type_id': self.picking_type_id.id,
            'product_id': product.id,
            'lot_id': lot.id,
            'qty': qty,
            'product_uom_id': product.uom_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'barcode_raw': self.barcode_input,
            'state': 'scanned',
            'company_id': self.session_id.company_id.id,
        })

        self.write({
            'barcode_input': False,
            'message': _(
                'Lote %(lot)s agregado: %(qty)s %(uom)s de %(product)s. '
                'Escanee el siguiente QR.'
            ) % {
                'lot': lot.display_name,
                'qty': qty,
                'uom': product.uom_id.name,
                'product': product.display_name,
            },
            'scan_alert_type': 'success',
            'kc_focus_token': (self.kc_focus_token or 0) + 1,
        })
        return self._reload_wizard()

    def _revalidate_all_lines(self):
        self.ensure_one()
        self._ensure_locations_configured()
        lines = self.session_id.line_ids
        if not lines:
            raise UserError(_('No hay lotes escaneados para transferir.'))

        lot_ids = lines.mapped('lot_id')
        if len(lot_ids) != len(lines):
            raise UserError(_('Este lote ya fue escaneado en esta sesión.'))

        barcode_values = lines.mapped('barcode_raw')
        if len(set(barcode_values)) != len(barcode_values):
            raise UserError(_('Este lote ya fue escaneado en esta sesión.'))

        for line in lines:
            product = line.product_id
            lot = line.lot_id
            if not product.exists():
                raise UserError(
                    _('Producto no encontrado para el código GS1: %s.') % (line.barcode_raw or '')
                )
            if not lot.exists() or lot.product_id != product:
                raise UserError(
                    _('El lote %(lot)s no existe para el producto %(product)s.')
                    % {'lot': lot.display_name, 'product': product.display_name}
                )
            self._get_available_qty_exact_location(
                product, lot, self.location_id, line.qty
            )

    @staticmethod
    def _set_move_line_quantity(move_line, qty):
        if 'quantity' in move_line._fields:
            move_line.quantity = qty
        elif 'qty_done' in move_line._fields:
            move_line.qty_done = qty
        else:
            raise UserError(_('No se encontró campo de cantidad en stock.move.line.'))
        if 'picked' in move_line._fields:
            move_line.picked = True

    def _process_validation_wizard(self, action, picking):
        if not isinstance(action, dict) or action.get('type') != 'ir.actions.act_window':
            return
        model = action.get('res_model')
        if not model:
            return
        ctx = dict(action.get('context') or {})
        if action.get('res_id'):
            wizard = self.env[model].browse(action['res_id']).with_context(**ctx)
        else:
            wizard = self.env[model].with_context(**ctx).create({})
        if model == 'stock.backorder.confirmation':
            wizard.process_cancel_backorder()
        elif model == 'stock.immediate.transfer' and hasattr(wizard, 'process'):
            wizard.process()
        picking.invalidate_recordset(['state'])

    def _mark_session_lots_low_quality(self):
        """Marca baja calidad en todos los lotes escaneados de la sesión."""
        self.ensure_one()
        if not self._picking_type_marks_low_quality():
            return
        lots = self.session_id.line_ids.mapped('lot_id')
        if 'low_quality' not in lots._fields:
            return
        lots.filtered(lambda lot: not lot.low_quality).write({'low_quality': True})

    def _validate_picking_done(self, picking):
        res = picking.button_validate()
        if isinstance(res, dict):
            self._process_validation_wizard(res, picking)
            if picking.state != 'done':
                res = picking.button_validate()
                if isinstance(res, dict):
                    self._process_validation_wizard(res, picking)
        if picking.state != 'done':
            raise UserError(
                _('No se pudo validar automáticamente la transferencia. Revise la operación creada: %s')
                % picking.display_name
            )

    def action_create_and_validate_transfer(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('Esta sesión ya fue finalizada.'))

        self._revalidate_all_lines()
        session = self.session_id
        company = session.company_id
        user = self.env.user

        grouped = defaultdict(list)
        for line in session.line_ids:
            grouped[line.product_id.id].append(line)

        origin = _('GS1 Interno %(session)s - %(user)s') % {
            'session': session.name,
            'user': user.name,
        }

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': origin,
            'company_id': company.id,
        })

        move_map = {}
        Move = self.env['stock.move']
        for product_id, lines in grouped.items():
            product = lines[0].product_id
            total_qty = sum(l.qty for l in lines)
            move = Move.create({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': total_qty,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'company_id': company.id,
            })
            move_map[product.id] = move

        picking.action_confirm()
        picking.move_line_ids.unlink()

        MoveLine = self.env['stock.move.line']
        for line in session.line_ids:
            move = move_map[line.product_id.id]
            move_line = MoveLine.create({
                'picking_id': picking.id,
                'move_id': move.id,
                'product_id': line.product_id.id,
                'lot_id': line.lot_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'product_uom_id': line.product_uom_id.id,
                'company_id': company.id,
            })
            self._set_move_line_quantity(move_line, line.qty)

        if 'picked' in picking.move_ids._fields:
            picking.move_ids.picked = True

        self._mark_session_lots_low_quality()

        self._validate_picking_done(picking)

        logs = self.env['kc.internal.lot.scan.log'].search([
            ('session_name', '=', session.name),
            ('state', '=', 'scanned'),
        ])
        logs.write({
            'picking_id': picking.id,
            'state': 'transferred',
        })

        session.write({
            'picking_id': picking.id,
            'state': 'done',
            'validated_date': fields.Datetime.now(),
            'mark_low_quality': self._picking_type_marks_low_quality(),
        })

        self.write({
            'state': 'done',
            'message': _(
                'Transferencia %(picking)s creada y validada correctamente.'
            ) % {'picking': picking.display_name},
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Transferencia interna GS1'),
            'res_model': 'kc.internal.lot.transfer.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_open_picking(self):
        self.ensure_one()
        if not self.session_id.picking_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transferencia'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.session_id.picking_id.id,
            'target': 'current',
        }
