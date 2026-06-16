# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Company(models.Model):
    _inherit = 'res.company'
    # ---------   Contingente de vacaciones    ---------------------------------------
    vacation_quota_table_ids = fields.One2many('hr.vacation.quota.table', 'company_id', string='Contingente de Vacaciones')
    # antiquity_bonus_table_ids = fields.One2many('hr.antiquity.bonus.table', 'company_id', string='Bono de Antigüedad')
    init_load_vacation_date = fields.Date(string='Carga inicial de vacaciones')


class HrVacationQuotaTable(models.Model):
    _name = 'hr.vacation.quota.table'
    _description = 'Contingente de Vacaciones'
    _rec_name = 'description'

    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    years_of_service_start = fields.Integer(string="Años de antiguedad comienzo")
    years_of_service_end = fields.Integer(string="Años de antiguedad fin")
    vacation_days = fields.Integer(string="Días de vacaciones")
    description = fields.Char(string="Descripción", readonly=True, compute='_compute_description', store=True)

    @api.depends('years_of_service_start', 'years_of_service_end', 'vacation_days')
    def _compute_description(self):
        years_of_service_start = 0
        years_of_service_end = 0
        vacation_days = 0
        for rec in self:
            if rec.years_of_service_start:
                years_of_service_start = rec.years_of_service_start
            if rec.years_of_service_end:
                years_of_service_end = rec.years_of_service_end
            if rec.vacation_days:
                vacation_days = rec.vacation_days
            rec.description = 'De ' + str(years_of_service_start) + ' a ' + str(years_of_service_end) + ' años de antigüedad ' + str(vacation_days) + ' días de vacaciones'


# class HrAntiquityBonusTable(models.Model):
#     _name = 'hr.antiquity.bonus.table'
#     _description = 'Bono de Antigüedad'
#     _rec_name = 'description'
#
#     company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
#     years_of_antiquity_bonus_start = fields.Integer(string="Años de antiguedad comienzo")
#     years_of_antiquity_bonus_end = fields.Integer(string="Años de antiguedad fin")
#     percentage = fields.Integer(string="Porciento")
#     description = fields.Char(string="Descripción", readonly=True, compute='_compute_description', store=True)
#
#     @api.depends('years_of_antiquity_bonus_start', 'years_of_antiquity_bonus_end', 'percentage')
#     def _compute_description(self):
#         years_of_antiquity_bonus_start = 0
#         years_of_antiquity_bonus_end = 0
#         percentage = 0
#         for rec in self:
#             if rec.years_of_antiquity_bonus_start:
#                 years_of_antiquity_bonus_start = rec.years_of_antiquity_bonus_start
#             if rec.years_of_antiquity_bonus_end:
#                 years_of_antiquity_bonus_end = rec.years_of_antiquity_bonus_end
#             if rec.percentage:
#                 percentage = rec.percentage
#             rec.description = 'De ' + str(years_of_antiquity_bonus_start) + ' a ' + str(years_of_antiquity_bonus_end) + ' años ' + str(percentage) + '%'
