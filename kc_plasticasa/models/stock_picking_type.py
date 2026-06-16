# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    kc_enable_gs1_dispatch_wizard = fields.Boolean(
        string='Activar wizard GS1 de lotes',
        help='Muestra el botón "Escanear GS1" en operaciones de este tipo.',
    )
    kc_gs1_block_duplicate_scan = fields.Boolean(
        string='Bloquear escaneo duplicado',
        default=True,
        help='Impide escanear el mismo QR o lote dos veces en la misma operación.',
    )
