# -*- coding: utf-8 -*-

from odoo import fields, models


class QualityAlert(models.Model):
    _inherit = 'quality.alert'

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Orden de trabajo',
        ondelete='set null',
        index=True,
        help='Orden de trabajo desde la que se generó esta alerta (opcional).',
    )
    by_stop_production = fields.Boolean(
        string='Por paro de producción',
        default=False,
        help='Tipo de paro de producción desde el que se generó esta solicitud de mantenimiento.',
    )
