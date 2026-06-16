from odoo import models, fields, api


class Survey(models.Model):
    _inherit = 'survey.survey'

    hr_survey_profile_id = fields.Many2one('hr.survey.profile', string='Perfil de encuesta')