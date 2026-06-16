# -*- coding: utf-8 -*-

import re

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    kc_lote_prefix = fields.Char(
        string='Prefijo de lote',
        help='Prefijo para lotes PT del asistente MRP (crear lote, pre-etiquetas, prod. manual). '
             'Formato: {prefijo}{número MO}-{secuencia}. Vacío = «LT».',
    )

    def kc_tablet_lot_prefix(self):
        """Prefijo alfanumérico para nombres de lote PT del asistente MRP."""
        self.ensure_one()
        raw = (self.kc_lote_prefix or '').strip() or 'LT'
        prefix = re.sub(r'[^A-Za-z0-9]', '', raw)
        return prefix or 'LT'

    kc_planning_location_ids = fields.One2many(
        'kc.sale.planning.location',
        'company_id',
        string='Ubicaciones planificación',
    )
    # Obsoletos: se migran a kc_planning_location_ids en post_init_hook.
    kc_planning_pt_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén PT (obsoleto)',
        help='Obsoleto. Use las ubicaciones en la pestaña Planificación MRP.',
    )
    kc_planning_mp_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén MP (obsoleto)',
        help='Obsoleto. Use las ubicaciones en la pestaña Planificación MRP.',
    )
