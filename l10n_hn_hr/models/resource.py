# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo import fields, models
from odoo.osv.expression import AND


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    resource_calendar_type_id = fields.Many2one('hr.resource.calendar.type', string='Tipo de horario de trabajo')