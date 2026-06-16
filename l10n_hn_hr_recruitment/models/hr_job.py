# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class HrJob(models.Model):
    _inherit = 'hr.job'

    internal_published = fields.Boolean(string="Publicado internamente")
    is_aux_published = fields.Boolean(string="Publicado")
    date_published = fields.Date(string="Fecha de publicación", readonly=False)
    hr_survey_profile_id = fields.Many2one('hr.survey.profile', string='Perfil de trabajo')
    no_of_recruit_perm = fields.Integer(string='Employees Permanents', copy=False,
                                          help='Number of new employees you expect to recruit permanently.', default=0)
    no_of_recruit_temp = fields.Integer(string='Employees Temporaries', copy=False,
                                          help='Number of new employees you expect to recruit temporality.', default=0)

    @api.onchange('internal_published')
    def onchange_internal_published(self):
        if self.internal_published:
            self.website_published = False
            self.date_published = date.today()
    @api.onchange('internal_published')
    def onchange_is_aux_published(self):
        if self.is_aux_published:
            self.is_published = True


    @api.model
    def compare_dates(self):
        _logger.info("CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> INIT")
        current_date = fields.Date.today()

        company_ids = self.env['res.company'].sudo().search([])
        _logger.info("CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> TOTAL COMPANIES TO CHECK %s" % len(company_ids))
        for company_id in company_ids:
            hr_job_ids = self.env['hr.job'].sudo().search([('internal_published', '=', True), ('company_id', '=', company_id.id)])
            _logger.info(
                "CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> TOTAL COMPANY JOBS TO CHECK %s" % len(hr_job_ids))
            for hr_job_id in hr_job_ids:
                target_date = hr_job_id.date_published + timedelta(days=company_id.day_internal_published)
                _logger.info("CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> name: %s" % hr_job_id.name)
                if current_date > target_date:
                    hr_job_id.date_published = False
                    hr_job_id.internal_published = False
                    hr_job_id.website_published = True
                    _logger.info("CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> COMPANY: %s JOB NAME: %s UPDATED" % (company_id.name, hr_job_id.name))

        _logger.info("CRON COMPARE DATES INTERNAL_PUBLISHED JOB -----> END")

    document_type_ids = fields.One2many('document.type', 'job_id', string='Document Types')