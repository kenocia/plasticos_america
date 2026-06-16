# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUser(models.Model):
    _inherit = 'res.users'

    kc_tablet_allow_mrp_workcenters = fields.Many2many(
        'mrp.workcenter',
        string='Centros de trabajo permitidos',
    )