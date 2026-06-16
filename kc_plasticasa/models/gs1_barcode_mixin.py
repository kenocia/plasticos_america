# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
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
_GS1_CONCATENATED_LAST_30_RE = re.compile(
    r'^240(?P<product>[\w./-]+?)10(?P<lot>.+)30(?P<qty>\d+)$',
    re.IGNORECASE,
)


class KcGs1BarcodeMixin(models.AbstractModel):
    _name = 'kc.gs1.barcode.mixin'
    _description = 'Parseo GS1 Plasticasa (AI 240, 10, 30) y utilidades de lote'

    kc_physical_allowed_location_ids = fields.Many2many(
        'stock.location',
        compute='_compute_kc_physical_allowed_location_ids',
        string='Ubicaciones permitidas (levantamiento físico)',
    )

    def _kc_physical_scan_company(self):
        self.ensure_one()
        return self.env.company

    def _kc_physical_scan_picking_type(self):
        self.ensure_one()
        return self.env['stock.picking.type'].browse()

    @api.depends()
    def _compute_kc_physical_allowed_location_ids(self):
        for record in self:
            company = record._kc_physical_scan_company()
            picking_type = record._kc_physical_scan_picking_type()
            loc_ids = record.kc_physical_reported_location_ids(
                company,
                picking_type or None,
            )
            record.kc_physical_allowed_location_ids = [(6, 0, loc_ids)]

    @api.model
    def _normalize_gs1_raw(self, barcode):
        raw = str(barcode).strip()
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
    def _parse_gs1_concatenated_last_30(self, raw):
        match = _GS1_CONCATENATED_LAST_30_RE.match(raw)
        if not match:
            return None
        product_code = (match.group('product') or '').strip()
        lot_name = (match.group('lot') or '').strip()
        qty_str = (match.group('qty') or '').strip()
        if not product_code or not lot_name or not qty_str or not qty_str.isdigit():
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
    def parse_gs1_barcode(self, barcode):
        """Parsea QR GS1 Plasticasa (AI 240, 10, 30) con o sin separador FNC1."""
        if not barcode or not str(barcode).strip():
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )
        raw = self._normalize_gs1_raw(barcode)
        if not raw.startswith('240'):
            raise UserError(_('QR inválido. El primer bloque debe iniciar con 240.'))
        parsed = self._parse_gs1_blocks(raw)
        if not parsed:
            parsed = self._parse_gs1_concatenated_last_30(raw)
        if not parsed:
            parsed = self._parse_gs1_concatenated(raw)
        if not parsed:
            compact = raw.replace(GS1_SEPARATOR, '')
            parsed = self._parse_gs1_concatenated_last_30(compact)
        if not parsed:
            compact = raw.replace(GS1_SEPARATOR, '')
            parsed = self._parse_gs1_concatenated(compact)
        if not parsed:
            raise UserError(
                _('QR inválido. No se encontraron los datos requeridos: producto, lote y cantidad.')
            )
        return parsed

    @api.model
    def kc_gs1_find_product(self, product_code):
        Product = self.env['product.product']
        domain_active = [('active', '=', True)]
        searches = [
            [('barcode', '=', product_code)],
            [('default_code', '=', product_code)],
            [('product_tmpl_id.default_code', '=', product_code)],
            [('product_tmpl_id.kc_gs1_code', '=', product_code)],
        ]
        for extra_domain in searches:
            product = Product.search(domain_active + extra_domain, limit=1)
            if product:
                return product
        return Product.browse()

    @api.model
    def kc_gs1_find_lot(self, product, lot_name, company=None):
        company = company or self.env.company
        return self.env['stock.lot'].search(
            [
                ('name', '=', lot_name),
                ('product_id', '=', product.id),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', company.id),
            ],
            limit=1,
        )

    @api.model
    def kc_lot_stock_company(self, lot, fallback_company=None):
        return lot.company_id or fallback_company or self.env.company

    @api.model
    def kc_lot_qty_in_internal_locations(self, lot, company=None):
        """Suma de quants del lote en ubicaciones de uso interno (informativo)."""
        company = self.kc_lot_stock_company(lot, company)
        Quant = self.env['stock.quant']
        domain = [
            ('lot_id', '=', lot.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '!=', 0),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        quants = Quant.search(domain)
        return sum(quants.mapped('quantity'))

    @api.model
    def kc_lot_qty_at_location(self, lot, location, company=None):
        """Existencia del lote en una ubicación concreta (quants)."""
        if not lot or not location:
            return 0.0
        company = self.kc_lot_stock_company(lot, company)
        Quant = self.env['stock.quant']
        domain = [
            ('lot_id', '=', lot.id),
            ('location_id', '=', location.id),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        quants = Quant.search(domain)
        return sum(quants.mapped('quantity'))

    @api.model
    def kc_lot_qty_on_hand(self, lot, company=None):
        """Existencia del lote en Odoo (todas las ubicaciones con stock > 0)."""
        company = self.kc_lot_stock_company(lot, company)
        quants = lot.quant_ids.filtered(
            lambda q: float_compare(q.quantity, 0.0, precision_digits=6) > 0
            and (not company or not q.company_id or q.company_id == company)
        )
        if quants:
            return sum(quants.mapped('quantity'))
        if company and lot.company_id == company:
            return lot.product_qty
        return 0.0

    @api.model
    def kc_lot_primary_system_location(self, lot, company=None):
        """Ubicación con mayor cantidad en inventario (cualquier uso)."""
        company = self.kc_lot_stock_company(lot, company)
        Quant = self.env['stock.quant']
        domain = [
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        best_loc = False
        best_qty = 0.0
        for quant in Quant.search(domain):
            if float_compare(quant.quantity, best_qty, precision_digits=6) > 0:
                best_qty = quant.quantity
                best_loc = quant.location_id
        return best_loc

    @api.model
    def kc_lot_system_location(self, lot, company=None):
        """Ubicación en Odoo: campo location_id del lote o mayor quant."""
        company = self.kc_lot_stock_company(lot, company)
        if lot.location_id:
            if not company or not lot.location_id.company_id or lot.location_id.company_id == company:
                return lot.location_id
        return self.kc_lot_primary_system_location(lot, company)

    @api.model
    def kc_lot_last_done_move_line(self, lot, company=None):
        """Última línea de movimiento validada del lote (trazabilidad)."""
        company = self.kc_lot_stock_company(lot, company)
        domain = [
            ('lot_id', '=', lot.id),
            ('state', '=', 'done'),
        ]
        if company:
            domain.append(('company_id', '=', company.id))
        return self.env['stock.move.line'].search(domain, order='date desc, id desc', limit=1)

    @api.model
    def kc_lot_last_done_picking(self, lot, company=None):
        """Último albarán validado que movió el lote."""
        line = self.kc_lot_last_done_move_line(lot, company)
        if line and line.picking_id:
            return line.picking_id
        return self.env['stock.picking'].browse()

    @api.model
    def kc_physical_reported_location_ids(self, company, picking_type=None):
        """Ubicaciones internas + rampas/despacho configuradas en compañía o tipo."""
        Location = self.env['stock.location']
        loc_ids = set(
            Location.search([
                ('usage', '=', 'internal'),
                ('company_id', 'in', [False, company.id]),
            ]).ids
        )
        loc_ids.update(company.kc_physical_scan_location_ids.ids)
        if picking_type:
            loc_ids.update(picking_type.kc_physical_scan_location_ids.ids)
        return list(loc_ids)
