# -*- coding: utf-8 -*-

from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    by_stop_production = fields.Boolean(
        string='Por paro de producción',
        default=False,
        help='Tipo de paro de producción desde el que se generó esta solicitud de mantenimiento.',
    )