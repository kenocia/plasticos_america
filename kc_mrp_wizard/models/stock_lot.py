# -*- coding: utf-8 -*-

import logging
import re
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_round

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = 'stock.lot'

    kc_prelabel_production_id = fields.Many2one(
        'mrp.production',
        string='Orden de fabricación',
        ondelete='restrict',
        index=True,
        help='Orden de fabricación de origen del lote: pre-etiqueta anticipada, producción tablet (PT) o lote de mala calidad.',
    )
    kc_prelabel_qty = fields.Float(
        string='Cantidad prevista pre-etiqueta',
        digits='Product Unit of Measure',
    )
    kc_prelabel_state = fields.Selection(
        [('none', 'No aplica'), ('pending', 'Pendiente de producir'), ('produced', 'Producido'), ('cancelled', 'Cancelado')],
        string='Estado etiqueta anticipada',
        default='none',
        copy=False,
    )
    kc_prelabel_shift = fields.Selection(
        [('A', 'Turno A (día)'), ('B', 'Turno B (noche)')],
        string='Turno pre-etiqueta',
        copy=False,
        help='Turno elegido al generar la pre-etiqueta; se imprime en la etiqueta junto al centro (p. ej. P01-A1).',
    )
    kc_prelabel_workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Centro de operación (pre-etiqueta)',
        copy=False,
        ondelete='set null',
        help='Centro usado al imprimir la pre-etiqueta; código en etiqueta (p. ej. P01 en P01-B2).',
    )
    kc_last_reprint_employee_id = fields.Many2one(
        'hr.employee',
        string='Última reimpresión por',
        copy=False,
        readonly=True,
    )
    kc_last_reprint_date = fields.Datetime(
        string='Última reimpresión',
        copy=False,
        readonly=True,
    )
    kc_reprint_count = fields.Integer(
        string='Reimpresiones',
        default=0,
        copy=False,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._kc_invalidate_mrp_prelabel_pending()
        return records

    def write(self, vals):
        if any(k in vals for k in ('kc_prelabel_state', 'kc_prelabel_production_id', 'kc_prelabel_qty')):
            mos = self.mapped('kc_prelabel_production_id')
        else:
            mos = self.env['mrp.production']
        res = super().write(vals)
        if any(k in vals for k in ('kc_prelabel_state', 'kc_prelabel_production_id', 'kc_prelabel_qty')):
            mos |= self.mapped('kc_prelabel_production_id')
            if mos:
                mos.invalidate_recordset(['kc_prelabel_pending_qty'])
        return res

    def unlink(self):
        mos = self.mapped('kc_prelabel_production_id')
        res = super().unlink()
        if mos:
            mos.invalidate_recordset(['kc_prelabel_pending_qty'])
        return res

    def _kc_invalidate_mrp_prelabel_pending(self):
        mo_ids = [x for x in self.mapped('kc_prelabel_production_id').ids if x]
        if mo_ids:
            self.env['mrp.production'].browse(list(set(mo_ids))).invalidate_recordset(['kc_prelabel_pending_qty'])

    def _kc_tablet_assert_can_reprint_label(self):
        """Valida que el lote pueda reimprimirse desde el asistente tablet."""
        self.ensure_one()
        if self.kc_prelabel_state == 'cancelled':
            raise UserError(
                _('El lote «%s» está cancelado y no se puede reimprimir la etiqueta.')
                % self.display_name
            )
        if not self.kc_prelabel_production_id:
            raise UserError(
                _('El lote «%s» no es un lote de producción del asistente MRP '
                  '(sin orden de fabricación vinculada).')
                % self.display_name
            )

    def _kc_tablet_record_label_reprint(self, employee):
        """Registra empleado y fecha de reimpresión."""
        self.ensure_one()
        self.sudo().write({
            'kc_last_reprint_employee_id': employee.id if employee else False,
            'kc_last_reprint_date': fields.Datetime.now(),
            'kc_reprint_count': (self.kc_reprint_count or 0) + 1,
        })

    def action_kc_prelabel_cancel(self):
        """Anula etiquetas solo en estado pendiente."""
        pending = self.filtered(lambda l: l.kc_prelabel_state == 'pending')
        if not pending:
            raise UserError(_('Solo se pueden cancelar lotes en estado «Pendiente de producir».'))
        extra = self - pending
        if extra:
            raise UserError(
                _('Algunos registros no están pendientes: %s') % ', '.join(extra.mapped('name'))
            )
        pending.write({'kc_prelabel_state': 'cancelled'})
        return True

    def kc_gs1_qty_for_barcode(self):
        """Pre-etiqueta pendiente: cantidad prevista sin inventario; misma física etiqueta que PT."""
        self.ensure_one()
        if self.kc_prelabel_state == 'pending':
            uom = self.product_id.uom_id
            qty = self.kc_prelabel_qty or 0.0
            if float_is_zero(qty, precision_rounding=uom.rounding):
                raise UserError(
                    _('No hay cantidad prevista configurada para generar la etiqueta GS1 de la pre-etiqueta.')
                )
            return qty
        return super().kc_gs1_qty_for_barcode()

    @api.model
    def kc_tablet_resolve_prelabel_scan_to_lot_name(self, scanned):
        """Nombre de `stock.lot` desde OCR humano/plano o cadena KC con grupos GS1 (`\\x1D`)."""
        text = (scanned or '').strip()
        if not text:
            return ''
        gs = '\x1D'
        if gs not in text:
            return text.strip()
        for chunk in text.split(gs):
            part = chunk.strip()
            if part.startswith('10') and len(part) > 2:
                return part[2:].strip()
        raise UserError(
            _('El código GS1 escaneado no contiene la aplicación «10» del lote. Pruebe a escanear de nuevo.')
        )

    @api.model
    def _kc_prelabel_company_domain(self, company):
        company = company or self.env.company
        return [('company_id', 'in', [company.id, False])]

    @api.model
    def _kc_prelabel_raise_not_available(self, lot, name, mo=None):
        """Mensaje explícito cuando el lote existe pero no puede añadirse a la lista."""
        state = lot.kc_prelabel_state or 'none'
        if state == 'produced':
            raise UserError(
                _('La pre-etiqueta «%s» ya fue producida y no puede volver a escanearse.')
                % name
            )
        if state == 'cancelled':
            raise UserError(
                _('La pre-etiqueta «%s» está cancelada y no está disponible para producir.')
                % name
            )
        if state == 'none':
            raise UserError(
                _('El lote «%s» existe en inventario pero no es una pre-etiqueta pendiente '
                  '(no tiene etiqueta anticipada activa).')
                % name
            )
        if state != 'pending':
            raise UserError(
                _('La pre-etiqueta «%s» no está disponible (estado: %s).')
                % (name, dict(lot._fields['kc_prelabel_state'].selection).get(state, state))
            )
        if mo and lot.kc_prelabel_production_id and lot.kc_prelabel_production_id != mo:
            raise UserError(
                _('La pre-etiqueta «%s» pertenece a la orden %s, no a %s.')
                % (name, lot.kc_prelabel_production_id.name, mo.name)
            )
        if mo and lot.product_id != mo.product_id:
            raise UserError(
                _('La pre-etiqueta «%s» es del producto «%s»; la orden %s fabrica «%s».')
                % (
                    name,
                    lot.product_id.display_name,
                    mo.name,
                    mo.product_id.display_name,
                )
            )
        if not lot.kc_prelabel_production_id:
            raise UserError(
                _('La pre-etiqueta «%s» no está vinculada a una orden de fabricación.')
                % name
            )
        raise UserError(
            _('La pre-etiqueta «%s» no está disponible para añadir a la lista.')
            % name
        )

    @api.model
    def kc_find_pending_prelabel_from_scan(self, raw, mo=None, company=None):
        """Localiza una pre-etiqueta **pendiente** por coincidencia **exacta** de nombre (o GS1 AI 10).

        No usa búsqueda parcial: evita confundir «LTP1015-132» con «LTP1015-1».

        :param mo: si se indica, el lote debe pertenecer a esa orden de fabricación.
        :param company: compañía para acotar búsqueda (por defecto compañía actual).
        """
        Lot = self.env['stock.lot']
        text = (raw or '').strip()
        if not text:
            raise UserError(_('Indique el código del lote.'))
        name = Lot.kc_tablet_resolve_prelabel_scan_to_lot_name(text)
        name = (name or '').strip()
        if not name:
            raise UserError(_('No se pudo interpretar el código escaneado.'))
        company = company or self.env.company
        base_domain = Lot._kc_prelabel_company_domain(company)
        lots = Lot.search(base_domain + [('name', '=', name)], limit=3)
        if len(lots) > 1:
            raise UserError(
                _('Hay más de un lote con el código exacto «%s». Contacte al administrador.')
                % name
            )
        if not lots:
            raise UserError(
                _('No existe ningún lote con el código exacto «%s». '
                  'Verifique el escaneo (debe coincidir letra por letra con la etiqueta).')
                % name
            )
        lot = lots[0]
        if lot.kc_prelabel_state != 'pending':
            Lot._kc_prelabel_raise_not_available(lot, name, mo=mo)
        if mo:
            if lot.kc_prelabel_production_id != mo:
                Lot._kc_prelabel_raise_not_available(lot, name, mo=mo)
            if lot.product_id != mo.product_id:
                Lot._kc_prelabel_raise_not_available(lot, name, mo=mo)
        elif not lot.kc_prelabel_production_id:
            raise UserError(
                _('La pre-etiqueta «%s» no está asignada a ninguna orden de fabricación.')
                % name
            )
        return lot

    def _kc_zpl_escape_gs1_qr_payload(self, gs1_value):
        """Adapta caracteres especiales GS1 (^ ~ \\ ASCII<32 _) para uso con ^FH en ^BQ ZPL."""
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

    def _kc_zpl_sanitize_text_line(self, text, max_len=56):
        """Texto seguro para ``^FD`` cuando la etiqueta usa ``^CI28`` (UTF-8 en Zebra).

        No convierte acentos/ñ a ``?``: el firmware imprime Unicode. Solo se omiten
        ``^``, ``~``, ``\\`` (rompen ZPL) y caracteres de control (excepto espacio/tab).
        """
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

    def _kc_zpl_wrap_words(self, text, max_chars=42):
        """Parte texto en líneas para ZPL (sin depender de ^FB/^TB y el firmware)."""
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

    def _kc_zebra_short_lot_display(self):
        """Lote compacto para ZPL: {prefijo}{MO}-{seq} (tablet) o legacy LT-PA-MO-01027-00005."""
        self.ensure_one()
        name = (self.name or '').strip().replace('/', '-')
        if re.match(r'^[A-Za-z0-9]+\d+-\d+$', name):
            return name
        m = re.search(r'MO-(\d+)-(\d+)$', name, re.IGNORECASE)
        if m:
            mo_num = m.group(1).lstrip('0') or '0'
            seq = m.group(2).lstrip('0') or '0'
            prefix = self.company_id.kc_tablet_lot_prefix() if self.company_id else 'LT'
            return '%s%s-%s' % (prefix, mo_num, seq)
        return self._kc_zpl_sanitize_text_line(name, 18)[:18]

    def _kc_zebra_label_date_str(self):
        """Fecha de creación del lote (re-impresión muestra la misma que la primera etiqueta)."""
        self.ensure_one()
        source = self.create_date or fields.Datetime.now()
        dt = fields.Datetime.context_timestamp(self, source)
        return dt.strftime('%d/%m/%Y')

    def _kc_zebra_label_time_str(self):
        """Hora de creación del lote en formato 24 h (misma instantánea que la fecha)."""
        self.ensure_one()
        source = self.create_date or fields.Datetime.now()
        dt = fields.Datetime.context_timestamp(self, source)
        return dt.strftime('%H:%M')

    @api.model
    def _kc_shift_letter_from_datetime(self, dt=None):
        """A = día [07:00, 19:00), B = noche; hora local del usuario."""
        source = dt or fields.Datetime.context_timestamp(self, fields.Datetime.now())
        minutes = source.hour * 60 + source.minute
        if 7 * 60 <= minutes < 19 * 60:
            return 'A'
        return 'B'

    def _kc_zebra_shift_letter_day_night(self):
        """Letra de turno por hora de creación del lote (lote PT directo en tablet)."""
        self.ensure_one()
        source = self.create_date or fields.Datetime.now()
        dt = fields.Datetime.context_timestamp(self, source)
        return self._kc_shift_letter_from_datetime(dt)

    def _kc_zebra_shift_letter_for_label(self, shift_letter=None):
        """Turno a imprimir: explícito (parámetro) > pre-etiqueta pendiente > hora del lote (PT tablet)."""
        self.ensure_one()
        if shift_letter in ('A', 'B'):
            return shift_letter
        # Solo pre-etiquetas pendientes usan el turno elegido en el wizard; «Crear lote PT» usa horario.
        if self.kc_prelabel_state == 'pending' and self.kc_prelabel_shift in ('A', 'B'):
            return self.kc_prelabel_shift
        return self._kc_zebra_shift_letter_day_night()

    def _kc_zebra_workcenter_for_label(self, workcenter=None):
        """Centro de operación para el código impreso (P01, E02, …)."""
        self.ensure_one()
        if workcenter:
            return workcenter
        if self.kc_prelabel_state == 'pending' and self.kc_prelabel_workcenter_id:
            return self.kc_prelabel_workcenter_id
        mo = self.kc_prelabel_production_id
        if mo:
            wo = mo.workorder_ids.filtered(lambda w: w.state != 'cancel')[:1]
            if wo:
                return wo.workcenter_id
        return self.env['mrp.workcenter']

    def _kc_zebra_turno_calidad_display(self, workcenter=None, shift_letter=None):
        """Texto turno+calidad en etiqueta: «P01-A1», «E02-B2» (centro + turno + grado)."""
        self.ensure_one()
        wc = self._kc_zebra_workcenter_for_label(workcenter)
        code = (wc.code or '').strip() if wc else ''
        if not code and wc:
            code = self._kc_zpl_sanitize_text_line((wc.name or '').strip(), 12)[:12]
        shift = self._kc_zebra_shift_letter_for_label(shift_letter)
        grade_code = '2' if getattr(self, 'low_quality', False) else '1'
        if code:
            return '%s-%s%s' % (code, shift, grade_code)
        return '%s%s' % (shift, grade_code)

    def _kc_zpl_name_has_grammage(self, name, grammage):
        """True si el nombre ya incluye el gramaje (p. ej. 24G / 24.0G)."""
        if not name or grammage is None:
            return False
        g = int(grammage) if grammage == int(grammage) else grammage
        return bool(re.search(r'%s\s*G\b' % re.escape(str(g)), name, re.IGNORECASE))

    def _kc_zpl_name_has_units_per_bale(self, name, units_per_bale):
        """True si el nombre ya incluye unidades por fardo (p. ej. 1X120 P)."""
        if not name or not units_per_bale:
            return False
        return bool(
            re.search(
                r'1X\s*%s\s*P\b' % re.escape(str(units_per_bale)),
                name,
                re.IGNORECASE,
            )
        )

    def _kc_zpl_product_name_body(self, product=None):
        """Descripción para etiqueta: no duplica gramo ni 1X…P si ya están en el nombre del producto."""
        self.ensure_one()
        product = product or self.product_id
        tmpl = product.product_tmpl_id
        name_body = (product.name or '').strip()
        if getattr(tmpl, 'grammage', None) and not self._kc_zpl_name_has_grammage(name_body, tmpl.grammage):
            name_body += ' %.1fG' % tmpl.grammage
        if getattr(tmpl, 'units_per_bale', None) and not self._kc_zpl_name_has_units_per_bale(
            name_body, tmpl.units_per_bale,
        ):
            name_body += ' 1X%s P' % tmpl.units_per_bale
        return name_body

    def _kc_build_zebra_lot_gs1_zpl(
        self,
        include_operator=True,
        include_shift_quality=True,
        workcenter=None,
        shift_letter=None,
    ):
        """ZPL ~50 mm ancho @203 dpi: márgenes, QR sin solapar ref/nombre; ref., nombre, operador y empresa en flujo
        continuo (sin pie reservado). La empresa se imprime centrada en el ancho útil con ``^FB`` (bloque de texto).

        :param include_operator: si False, omite el bloque «Operador» (p. ej. etiqueta materia prima en Plasticasa).
        :param include_shift_quality: si False, omite el código turno/calidad (A1, B2, etc.; solo fabricación).

        Distribución vertical del cuerpo: el nombre puede ocupar varias líneas consecutivas; si cabe en
        una sola línea se deja la siguiente vacía antes del operador. Operador y empresa se reservan
        siempre en el pie de la etiqueta (``footer_reserve``).

        Ajuste de tipografía Zebra: cada ``^A0N,h,w`` = fuente escalable A, orientación N, **alto y ancho en dots**
        (203 dpi → ~8 dots ≈ 1 mm de alto de letra). Más alto = letra más grande (ocupa más líneas en papel).

        Truncado: ``_kc_zpl_sanitize_text_line(texto, max_len)`` corta el string a **max_len caracteres** antes
        de quitar caracteres peligrosos para ZPL. ``_kc_zpl_wrap_words(texto, max_chars)`` parte por **palabras**
        en líneas de como mucho ``max_chars`` caracteres (sin medir mm: si subes max_chars, caben más letras
        por línea si el ancho físico de la etiqueta lo permite; si te pasas, el texto se sale por la derecha).
        """
        self.ensure_one()
        # --- Parámetros visibles (editar aquí) ---
        font_lote = (26, 26)  # (alto, ancho) dots — lote corto arriba derecha
        font_cant = (20, 20)
        font_fecha = (20, 20)
        font_hora = (20, 20)
        font_turno_calidad = (20, 20)
        font_ref = (20, 20)
        # font_nombre_etiq = (20, 20)  # línea "Nombre:"
        font_nombre_body = (20, 16)  # descripción del producto (varias líneas)
        # QR en ZPL: ``^BQN,modelo,magnificación`` — la magnificación (1–10) fija el **tamaño en dots**
        # del módulo en la **impresora** (no confundir con el QR en pantalla/PDF de Odoo).
        qr_model = 2  # 1 o 2 según manual Zebra (^BQ)
        qr_magnification = 5  # subir p.ej. 6 u 8 para QR más grande; si solapa texto, sube solo y_after_qr abajo
        font_operador = (20, 20)
        font_empresa = (20, 20)
        nombre_max_chars_por_linea = 50  # wrap del nombre producto (subir p.ej. 42–46 si cabe en su papel)
        nombre_sanitize_por_linea = 48  # tope por línea tras wrap (seguridad ZPL)
        nombre_truncar_ultima = 40  # última línea cortada con "..." si no cabe más altura

        company = self.company_id or self.product_id.company_id or self.env.company
        empresa_raw = (company.name or '').strip()
        if not empresa_raw and company.partner_id:
            empresa_raw = (company.partner_id.name or '').strip()
        if not empresa_raw:
            empresa_raw = (self.env.company.name or '').strip() or '-'

        name_body = self._kc_zpl_sanitize_text_line(self._kc_zpl_product_name_body(), 200)

        qty_line = _('Cant.: —')
        uom = self.product_id.uom_id
        try:
            qty_val = float_round(
                self.kc_gs1_qty_for_barcode(),
                precision_rounding=uom.rounding,
            )
            qty_line = _('Cant.: %(qty)s %(uom)s') % {'qty': qty_val, 'uom': uom.name or ''}
        except UserError:
            qty_line = _('Cant.: —')

        short_lot = self._kc_zebra_short_lot_display()
        fecha = _('Fecha: %s') % self._kc_zebra_label_date_str()
        hora = _('Hora: %s') % self._kc_zebra_label_time_str()
        operador = None
        if include_operator:
            operador = _('Operador: %s') % (
                self._kc_zpl_sanitize_text_line(self.kc_employee_id.name, 44)
                if self.kc_employee_id else '-'
            )
        empresa = self._kc_zpl_sanitize_text_line(empresa_raw, 120) or '-'

        # 203 dpi: ~50 mm ancho = 406 dots; alto lógico para texto en flujo hasta cerca del borde inferior
        pw = 406
        ll = 520
        ml = 22  # margen izquierda
        mt = 20  # margen superior
        # Primer Y del texto bajo el QR (depende de magnificación + longitud GS1; fórmula orientativa en dots)
        y_after_qr = mt + max(120, 64 + qr_magnification * 28)
        margin_bottom = 16  # tope vertical genérico (no reservar pie fijo)

        zpl_parts = [
            '^XA\n',
            '^PW%d\n' % pw,
            '^LL%d\n' % ll,
            '^LH0,0\n',
            '^CI28\n',
        ]
        # QR GS1 arriba izquierda (con margen)
        try:
            gs1 = self.kc_build_gs1_scan_value()
            esc = self._kc_zpl_escape_gs1_qr_payload(gs1)
            zpl_parts.append(
                '^FO%d,%d^BQN,%d,%d^FH^FDLA,%s^FS\n'
                % (ml, mt, qr_model, qr_magnification, esc),
            )
        except UserError as err:
            _logger.info('KC Zebra: QR GS1 omitido (%s); Code128.', err)
            zpl_parts.append(
                '^FO%d,%d^BY2\n^BCN,52,Y,N,N\n^FD%s^FS\n'
                % (ml, mt, self._kc_zpl_sanitize_text_line(self.name, 28)),
            )
        # Columna derecha (lote, cant., fecha) — alineada a la derecha del ancho útil
        rx = ml + 165
        zpl_parts.append(
            '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
            % (rx, mt+10, font_lote[0], font_lote[1], self._kc_zpl_sanitize_text_line(short_lot, 22)),
        )
        zpl_parts.append(
            '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
            % (rx, mt + 40, font_cant[0], font_cant[1], self._kc_zpl_sanitize_text_line(qty_line, 30)),
        )
        zpl_parts.append(
            '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
            % (rx, mt + 66, font_fecha[0], font_fecha[1], self._kc_zpl_sanitize_text_line(fecha, 34)),
        )
        zpl_parts.append(
            '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
            % (rx, mt + 92, font_hora[0], font_hora[1], self._kc_zpl_sanitize_text_line(hora, 34)),
        )
        # Turno + grado (A1, B2, …): solo etiqueta de fabricación / tablet PT.
        if include_shift_quality:
            turno_calidad = self._kc_zebra_turno_calidad_display(
                workcenter=workcenter,
                shift_letter=shift_letter,
            )
            y_turno = mt + 92 + font_hora[0] + 4
            zpl_parts.append(
                '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
                % (
                    rx,
                    y_turno,
                    font_turno_calidad[0],
                    font_turno_calidad[1],
                    self._kc_zpl_sanitize_text_line(turno_calidad, 34),
                ),
            )
        y_mid = y_after_qr - 40
        y_max_body = ll - margin_bottom
        line_step = font_nombre_body[0] + 4
        op_step = font_operador[0] + 4
        emp_h, emp_w = font_empresa[0], font_empresa[1]
        emp_fb_lines = 3
        emp_line_gap = max(2, emp_h // 2)
        # Reservar pie fijo: operador (opcional) + empresa (últimas líneas de la etiqueta).
        footer_reserve = emp_h * emp_fb_lines + emp_line_gap * 2
        if include_operator:
            footer_reserve += op_step
        y_max_name = max(y_mid, y_max_body - footer_reserve)

        if self.product_id.default_code:
            ref_txt = self._kc_zpl_sanitize_text_line(self.product_id.default_code, 50)
            zpl_parts.append(
                '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
                % (ml, y_mid, font_ref[0], font_ref[1], ref_txt),
            )
            y_mid += font_ref[0] + 6

        name_lines = self._kc_zpl_wrap_words(name_body, max_chars=nombre_max_chars_por_linea)
        for idx, ln in enumerate(name_lines):
            if y_mid + line_step > y_max_name:
                zpl_parts.append(
                    '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
                    % (
                        ml,
                        y_mid,
                        font_nombre_body[0],
                        font_nombre_body[1],
                        self._kc_zpl_sanitize_text_line(
                            ln[: max(1, nombre_truncar_ultima - 3)] + '...',
                            nombre_truncar_ultima,
                        ),
                    ),
                )
                break
            safe = self._kc_zpl_sanitize_text_line(ln, nombre_sanitize_por_linea)
            zpl_parts.append(
                '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
                % (ml, y_mid, font_nombre_body[0], font_nombre_body[1], safe),
            )
            is_last = idx >= len(name_lines) - 1
            if not is_last:
                # Nombre en varias líneas: la siguiente línea continúa el texto (sin hueco).
                y_mid += line_step
            elif len(name_lines) == 1:
                # Una sola línea de nombre: hueco antes del pie (operador o empresa).
                y_mid += line_step * (2 if include_operator else 1)
            else:
                y_mid += line_step

        if include_operator and operador:
            # Operador: penúltimo bloque de texto (alineado a la izquierda).
            for oln in self._kc_zpl_wrap_words(operador, max_chars=nombre_max_chars_por_linea)[:3]:
                if y_mid + op_step > y_max_body:
                    break
                zpl_parts.append(
                    '^FO%d,%d^A0N,%d,%d^FD%s^FS\n'
                    % (ml, y_mid, font_operador[0], font_operador[1], self._kc_zpl_sanitize_text_line(oln, 52)),
                )
                y_mid += op_step

        # Empresa: última línea(s) centrada(s) en el ancho útil.
        block_w = max(60, pw - 2 * ml)
        if y_mid + emp_h * emp_fb_lines + emp_line_gap * 2 <= y_max_body:
            zpl_parts.append(
                '^FO%d,%d^A0N,%d,%d^FB%d,%d,%d,C,0^FD%s^FS\n'
                % (ml, y_mid, emp_h, emp_w, block_w, emp_fb_lines, emp_line_gap, empresa),
            )

        zpl_parts.append('^XZ\n')
        return ''.join(zpl_parts)

    def kc_send_lot_label_to_network_printer(self, printer, workcenter=None, shift_letter=None):
        """Imprime etiqueta GS1/ZPL por RAW TCP si `printer` es un ``network.printer``."""
        self.ensure_one()
        if not printer:
            return {'success': False, 'error': _('No hay impresora de etiquetas en el centro.')}
        zpl = self._kc_build_zebra_lot_gs1_zpl(
            workcenter=workcenter,
            shift_letter=shift_letter,
        )
        return printer.send_tcp_raw_binary(zpl.encode('utf-8', errors='replace'))

    def _kc_report_prelabel_print(self):
        """Misma etiqueta de lote (GS1/pequeño formato) que el producto ya terminado."""
        self.ensure_one()
        report = self.env.ref(
            'kc_plasticasa.action_report_kc_lot_label',
            raise_if_not_found=False,
        )
        if not report:
            return True
        return report.report_action(self)
