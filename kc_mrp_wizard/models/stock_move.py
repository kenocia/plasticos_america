# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    kc_semi_adjustment_production_id = fields.Many2one(
        'mrp.production',
        string='MO (ajuste semi)',
        index=True,
        copy=False,
        readonly=True,
        help='Orden de fabricación asociada cuando el movimiento se generó desde el asistente de salida de semi.',
    )
