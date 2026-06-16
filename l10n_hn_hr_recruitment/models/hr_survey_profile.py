# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrSurveyProfile(models.Model):
    _name = 'hr.survey.profile'

    name = fields.Char(string='Perfil')