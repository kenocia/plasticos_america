# -*- coding: utf-8 -*-

import logging
import re
import unicodedata
import urllib.parse

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.barcode import get_barcode_check_digit
from odoo.tools.float_utils import float_is_zero, float_round


_logger = logging.getLogger(__name__)


def _kc_gtin14_for_gs1_ai01(numeric_barcode):
    """14 dígitos para AI (01) con dígito de control válido (misma validación que el cliente Odoo)."""
    b = (numeric_barcode or '').strip()
    if not b.isdigit() or len(b) < 12:
        return None
    if len(b) in (12, 13, 14):
        candidate = b.zfill(14)[-14:]
    else:
        candidate = b[:14]
    if len(candidate) != 14:
        return None
    pad18 = ('0' * (18 - len(candidate))) + candidate
    check = get_barcode_check_digit(pad18)
    if int(candidate[-1]) != check:
        candidate = candidate[:-1] + str(check)
    return candidate


class StockLot(models.Model):
    _inherit = 'stock.lot'

    low_quality = fields.Boolean(string='Baja Calidad', tracking=True)
    kc_employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        ondelete='restrict',
        index=True,
        tracking=True,
        help='Tablet: empleado al crear/producir lote PT o baja calidad. Pre-etiquetas: opcional al generar; '
             'si queda vacío, asígnelo manualmente en el lote. No se sustituye al escanear y producir.',
    )
    def _kc_label_company(self):
        self.ensure_one()
        return self.product_id.company_id or self.env.company

    def kc_label_lang(self):
        self.ensure_one()
        return self._kc_label_company().partner_id.lang or 'es_ES'

    def kc_label_qty_available(self):
        """Existencia del lote (suma de quants) en la UdM del producto."""
        self.ensure_one()
        company = self._kc_label_company()
        domain = [('lot_id', '=', self.id), ('quantity', '>', 0)]
        if company:
            domain.append(('company_id', '=', company.id))
        quants = self.env['stock.quant'].search(domain)
        total = sum(quants.mapped('quantity'))
        uom = self.product_id.uom_id
        return float_round(total, precision_rounding=uom.rounding)

    def kc_gs1_qty_for_barcode(self):
        """Cantidad codificada en AI 30/403 al construir el GS1 (existencia disponible estándar)."""
        self.ensure_one()
        uom = self.product_id.uom_id
        qty = self.kc_label_qty_available()
        if float_is_zero(qty, precision_rounding=uom.rounding):
            raise UserError(
                _('No hay existencia en inventario para el lote %s; no se puede generar el código GS1.')
                % self.display_name
            )
        return qty

    def kc_build_gs1_scan_value(self):
        """Cadena GS1 (FNC1 entre AIs) alineada con nomenclatura LOTES: 01/240, 10, 30; + 40x si UdM es peso."""
        self.ensure_one()
        sep = '\x1D'
        product = self.product_id
        uom = product.uom_id
        parts = []

        barcode = (product.barcode or '').strip()
        used_ai01 = False
        if barcode.isdigit():
            if len(barcode) in (12, 13, 14):
                gtin14 = _kc_gtin14_for_gs1_ai01(barcode)
                if gtin14:
                    parts.append(f'01{gtin14}')
                    used_ai01 = True
            elif len(barcode) > 14:
                # Código numérico largo en ficha: primeros 14 dígitos como GTIN-14 (AI 01).
                gtin14 = _kc_gtin14_for_gs1_ai01(barcode[:14])
                if gtin14:
                    parts.append(f'01{gtin14}')
                    used_ai01 = True
        if not used_ai01:
            if product.default_code:
                code = re.sub(r'[^\w./-]', '', (product.default_code or '').strip())
                if not code:
                    raise UserError(_('La referencia interna del producto no es válida para GS1 (240).'))
                parts.append(f'240{code}')
            else:
                raise UserError(
                    _('El producto %s no tiene código de barras GTIN ni referencia interna para la etiqueta GS1.')
                    % product.display_name
                )

        lot_name = (self.name or '').strip()
        if not lot_name or sep in lot_name or '#' in lot_name:
            raise UserError(_('El nombre de lote contiene caracteres no permitidos en GS1 (10).'))
        parts.append(f'10{lot_name}')

        qty = self.kc_gs1_qty_for_barcode()

        kgm_categ = self.env.ref('uom.product_uom_categ_kgm', raise_if_not_found=False)
        is_weight = kgm_categ and uom.category_id == kgm_categ

        if is_weight:
            grams = int(float_round(qty * 1000, precision_digits=0))
            if grams < 0 or grams > 999999:
                raise UserError(_('Cantidad en kg fuera de rango para el AI 403 (6 dígitos).'))
            parts.append(f'403{grams:06d}')
        else:
            qty_int = int(float_round(qty, precision_rounding=uom.rounding))
            if qty_int < 0 or qty_int > 999999999:
                raise UserError(_('Cantidad fuera de rango para el AI 30.'))
            parts.append(f'30{qty_int}')

        return sep.join(parts)

    def kc_gs1_qr_src(self):
        self.ensure_one()
        value = self.kc_build_gs1_scan_value()
        # Odoo 18: report_barcode(barcode_type, value) — query debe usar barcode_type, no type.
        # Bitmap moderado: en PDF wkhtmltopdf a veces ignora CSS y muestra el PNG a tamaño nativo.
        query = urllib.parse.urlencode({
            'barcode_type': 'QR',
            'value': value,
            'width': 200,
            'height': 200,
            'humanreadable': 0,
        })
        return '/report/barcode/?%s' % query

    def kc_lot_label_qr_block(self):
        """Para QWeb: no lanzar excepción; devolver src del QR o texto de error para mostrar al usuario."""
        self.ensure_one()
        try:
            return {'src': self.kc_gs1_qr_src(), 'error': ''}
        except UserError as e:
            return {'src': False, 'error': e.args[0] if e.args else str(e)}
        except Exception:
            _logger.exception('kc_lot_label_qr_block: lote %s', self.id)
            return {
                'src': False,
                'error': _(
                    'No se pudo generar el código QR. Revise existencia, producto y nombre de lote, o consulte el registro de errores.'
                ),
            }

    def _kc_sp_zpl_sanitize(self, text, max_len=56):
        """Igual que kc_mrp: UTF-8 con ``^CI28``; conserva tildes y ñ en texto visible."""
        raw = unicodedata.normalize('NFC', (text or '')).strip()
        if max_len:
            raw = raw[:max_len]
        out = []
        for c in raw:
            o = ord(c)
            if c in '^~\\':
                continue
            if o < 32 and c not in '\t ':
                continue
            if 0xD800 <= o <= 0xDFFF:
                continue
            out.append(c)
        return ''.join(out) or '-'

    def _kc_sp_zpl_wrap(self, text, max_chars=40):
        words = (text or '').split()
        if not words:
            return ['-']
        lines = []
        cur = []
        for w in words:
            cand = ' '.join(cur + [w])
            if len(cand) <= max_chars:
                cur.append(w)
            else:
                if cur:
                    lines.append(' '.join(cur))
                cur = [w]
        if cur:
            lines.append(' '.join(cur))
        return lines

    def _kc_sp_zpl_escape_gs1_qr(self, gs1_value):
        esc = []
        for ch in (gs1_value or ''):
            o = ord(ch)
            if ch == '_':
                esc.append('_5F')
            elif o < 32 or ch in ('^', '~', '\\'):
                esc.append('_%02X' % o)
            elif o >= 127:
                esc.append('?')
            else:
                esc.append(ch)
        return ''.join(esc)

    def _kc_supplier_reception_qty(self, picking):
        self.ensure_one()
        if not picking:
            return self.kc_label_qty_available()
        lines = picking.move_line_ids.filtered(lambda ml: ml.lot_id and ml.lot_id.id == self.id)
        qty = sum(lines.mapped('quantity'))
        uom = self.product_id.uom_id
        return float_round(qty, precision_rounding=uom.rounding)

    def _kc_build_supplier_reception_zebra_zpl(self, picking=None):
        """ZPL recepción proveedor: distinto al de fabricación; lote completo, proveedor, usuario recepción."""
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id
        company = self._kc_label_company()

        name_body = (self.product_id.name or '').strip()
        if getattr(tmpl, 'grammage', None):
            name_body += ' %.1fG' % tmpl.grammage
        if getattr(tmpl, 'units_per_bale', None):
            name_body += ' 1X%s P' % tmpl.units_per_bale
        name_body = self._kc_sp_zpl_sanitize(name_body, 200)

        uom = self.product_id.uom_id
        qty = self._kc_supplier_reception_qty(picking)
        qty_line = _('Cant.: %(qty)s %(uom)s') % {'qty': qty, 'uom': uom.name or ''}

        lot_disp = self._kc_sp_zpl_sanitize(self.name, 28)
        fecha_src = picking.date_done if picking and picking.date_done else fields.Datetime.now()
        dt = fields.Datetime.context_timestamp(self, fecha_src)
        fecha = _('FECHA: %s') % dt.strftime('%d/%m/%Y')
        prov = picking.partner_id.display_name if picking and picking.partner_id else '-'
        prov = self._kc_sp_zpl_sanitize(prov, 36)
        recibido = self._kc_sp_zpl_sanitize(self.env.user.name, 32)
        empresa = self._kc_sp_zpl_sanitize(company.name, 46) or '-'

        zpl_parts = [
            '^XA\n',
            '^PW406\n',
            '^LL400\n',
            '^LH0,0\n',
            '^CI28\n',
            '^FO12,4^A0N,14,14^FD%s^FS\n' % self._kc_sp_zpl_sanitize(_('RECEPCIÓN PROVEEDOR'), 24),
        ]
        try:
            gs1 = self.kc_build_gs1_scan_value()
            esc = self._kc_sp_zpl_escape_gs1_qr(gs1)
            zpl_parts.append('^FO8,24^BQN,2,4^FH^FDLA,%s^FS\n' % esc)
        except UserError as err:
            _logger.debug('KC supplier ZPL: sin QR GS1 (%s); Code128.', err)
            zpl_parts.append(
                '^FO8,24^BY2\n^BCN,48,Y,N,N\n^FD%s^FS\n' % self._kc_sp_zpl_sanitize(self.name, 28),
            )

        rx = 210
        zpl_parts.append('^FO%d,28^A0N,18,18^FD%s: %s^FS\n' % (rx, self._kc_sp_zpl_sanitize(_('Lote'), 8), lot_disp))
        zpl_parts.append('^FO%d,52^A0N,15,15^FD%s^FS\n' % (rx, self._kc_sp_zpl_sanitize(qty_line, 32)))
        zpl_parts.append('^FO%d,74^A0N,13,13^FD%s^FS\n' % (rx, self._kc_sp_zpl_sanitize(fecha, 34)))

        y_mid = 120
        if self.product_id.default_code:
            ref_txt = _('Ref.: %s') % self._kc_sp_zpl_sanitize(self.product_id.default_code, 36)
            zpl_parts.append('^FO12,%d^A0N,13,13^FD%s^FS\n' % (y_mid, ref_txt))
            y_mid += 18
        zpl_parts.append('^FO12,%d^A0N,10,10^FD%s:^FS\n' % (y_mid, _('Nombre')))
        y_mid += 14
        for ln in self._kc_sp_zpl_wrap(name_body, 40):
            zpl_parts.append('^FO12,%d^A0N,10,10^FD%s^FS\n' % (y_mid, self._kc_sp_zpl_sanitize(ln, 46)))
            y_mid += 13
        zpl_parts.append(
            '^FO12,%d^A0N,12,12^FD%s %s^FS\n'
            % (y_mid, self._kc_sp_zpl_sanitize(_('Proveedor:'), 14), prov)
        )
        y_mid += 16
        if self.low_quality:
            zpl_parts.append(
                '^FO12,%d^A0N,12,12^FD*** %s ***^FS\n'
                % (y_mid, self._kc_sp_zpl_sanitize(_('Baja calidad'), 22))
            )
            y_mid += 14
        y_bot = max(y_mid + 8, 288)
        zpl_parts.append(
            '^FO12,%d^A0N,12,12^FD%s: %s^FS\n'
            % (y_bot, self._kc_sp_zpl_sanitize(_('Recepción'), 12), recibido)
        )
        zpl_parts.append('^FO100,%d^A0N,11,11^FD%s^FS\n' % (y_bot + 22, empresa))
        zpl_parts.append('^XZ\n')
        return ''.join(zpl_parts)

    def _kc_zpl_add_top_banner_to_gs1_label(self, zpl, banner_text, y_shift=20, y_threshold=20, margin_left=22):
        """Inserta rótulo superior y desplaza ``^FO`` con Y >= umbral (etiqueta GS1 de kc_mrp_wizard)."""
        marker = '^CI28\n'
        if marker not in zpl:
            raise UserError(_('No se pudo aplicar el rótulo de materia prima al ZPL del lote.'))
        banner_line = '^FO%d,4^A0N,14,14^FD%s^FS\n' % (
            margin_left,
            self._kc_sp_zpl_sanitize(banner_text, 24),
        )
        head, tail = zpl.split(marker, 1)

        def _shift_fo_y(match):
            x, y = int(match.group(1)), int(match.group(2))
            if y >= y_threshold:
                return '^FO%d,%d' % (x, y + y_shift)
            return match.group(0)

        tail_shifted = re.sub(r'\^FO(\d+),(\d+)', _shift_fo_y, tail)
        return head + marker + banner_line + tail_shifted

    def _kc_build_raw_material_zebra_zpl(self):
        """Etiqueta GS1 (kc_mrp_wizard): «MATERIA PRIMA», sin Operador ni código turno/calidad (A1, B2…)."""
        self.ensure_one()
        build_gs1 = getattr(self, '_kc_build_zebra_lot_gs1_zpl', None)
        if not callable(build_gs1):
            raise UserError(
                _('La etiqueta de materia prima requiere el módulo «KenoCia MRP Wizard» (kc_mrp_wizard).')
            )
        return self._kc_zpl_add_top_banner_to_gs1_label(
            build_gs1(include_operator=False, include_shift_quality=False),
            _('MATERIA PRIMA'),
        )

    def action_kc_print_lot_label(self):
        """Abre el asistente de impresión Zebra/PDF (uno o varios lotes)."""
        lots = self.filtered(lambda lot: lot.id)
        if not lots:
            raise UserError(_('Seleccione al menos un lote.'))
        wiz = self.env['kc.lot.label.print.wizard'].create({
            'lot_ids': [(6, 0, lots.ids)],
            'label_profile': 'manufacturing',
        })
        title = _('Etiqueta Zebra') if len(lots) == 1 else _('Etiquetas Zebra (%s)') % len(lots)
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'kc.lot.label.print.wizard',
            'view_mode': 'form',
            'res_id': wiz.id,
            'target': 'new',
        }
