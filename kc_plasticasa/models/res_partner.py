# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    scan_lote_quality_low = fields.Boolean(
        string='Baja calidad',
        help='Marcar si el cliente permite escanear(entregas) lotes con baja calidad'
    )

    delivery_excess_max_percent = fields.Float(
        string='Máx. % excedente sobre pedido',
        help='Porcentaje máximo de excedente permitido sobre la cantidad pedida en cada línea de venta, '
             'comparando lo ya entregado (albaranes confirmados) más lo que se valida en este albarán. '
             '0 o vacío: no se permite exceder la cantidad pedida.',
    )