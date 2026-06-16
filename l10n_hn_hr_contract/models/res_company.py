# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Company(models.Model):
    _inherit = 'res.company'
    alert_contract = fields.Integer(string='Alerta de vencimiento de contrato (días)', default=10)
    previous_quit_notice_ids = fields.One2many('hr.table.previous.quit.notice', 'company_id', string='Notificación previa de renuncia')


class HrTablePreviousQuitNotice(models.Model):
    _name = 'hr.table.previous.quit.notice'
    _description = 'Tabla de notificación de baja'
    _rec_name = 'description'

    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    years_of_service_start = fields.Integer(string="Años de antiguedad comienzo")
    month_of_service_start = fields.Integer(string="Meses de antiguedad comienzo")
    month_of_service_total_start = fields.Integer(string="Meses de antiguedad comienzo",
                                                  compute='_compute_month_of_service_total_start', store=True)
    years_of_service_end = fields.Integer(string="Años de antiguedad fin")
    month_of_service_end = fields.Integer(string="Meses de antiguedad fin")
    month_of_service_total_end = fields.Integer(string="Meses de antiguedad fin",
                                                compute='_compute_month_of_service_total_end', store=True)
    previous_days = fields.Integer(string="Días previos a solicitar la renuncia")
    penalty_to_be_applied = fields.Float(string="Multa a aplicar")
    description = fields.Char(string="Descripción", readonly=True, compute='_compute_description', store=True)

    @api.depends('years_of_service_start', 'month_of_service_start', 'years_of_service_end', 'month_of_service_end', 'previous_days')
    def _compute_description(self):
        years_of_service_start = 0
        month_of_service_start = 0
        years_of_service_end = 0
        month_of_service_end = 0
        previous_days = 0
        for rec in self:
            if rec.years_of_service_start:
                years_of_service_start = rec.years_of_service_start
            if rec.month_of_service_start:
                month_of_service_start = rec.month_of_service_start
            if rec.years_of_service_end:
                years_of_service_end = rec.years_of_service_end
            if rec.month_of_service_end:
                month_of_service_end = rec.month_of_service_end
            if rec.previous_days:
                previous_days = rec.previous_days
                rec.month_of_service_total_end += rec.month_of_service_end
            rec.description = 'De ' + str(years_of_service_start) + '.' + str(month_of_service_start) + ' a ' + str(years_of_service_end) + '.' + str(month_of_service_end)+ ' años de antigüedad ' + str(previous_days) + ' días previos'

    @api.depends('years_of_service_start', 'month_of_service_start')
    def _compute_month_of_service_total_start(self):
        for rec in self:
            rec.month_of_service_total_start = 0
            if rec.years_of_service_start:
                rec.month_of_service_total_start = rec.years_of_service_start * 12
            if rec.month_of_service_start:
                rec.month_of_service_total_start += rec.month_of_service_start

    @api.depends('years_of_service_end', 'month_of_service_end')
    def _compute_month_of_service_total_end(self):
        for rec in self:
            rec.month_of_service_total_end = 0
            if rec.years_of_service_end:
                rec.month_of_service_total_end = rec.years_of_service_end * 12
            if rec.month_of_service_end:
                month_of_service_end = rec.month_of_service_end
