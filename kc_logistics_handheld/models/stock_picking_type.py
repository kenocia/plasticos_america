# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    kc_enable_internal_lot_scanner = fields.Boolean(
        string='Disponible en wizard interno GS1',
        default=True,
        help='Permite seleccionar este tipo de operación en el wizard de transferencia interna GS1.',
    )
    kc_mark_low_quality = fields.Boolean(
        string='Marcar lotes como baja calidad',
        help='Si está activo, al validar la transferencia GS1 se marca baja calidad '
             'en todos los lotes escaneados.',
    )
