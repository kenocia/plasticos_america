# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    day_internal_published = fields.Integer(related='company_id.day_internal_published', readonly=False)
    selection_portal = fields.Many2many(related='company_id.selection_portal', readonly=False)