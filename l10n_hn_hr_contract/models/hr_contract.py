# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class HrContract(models.Model):
    _inherit = 'hr.contract'

    is_perifoneo = fields.Boolean('Perifoneo', default=False)
    is_animador = fields.Boolean('Animador', default=False)

    job_id = fields.Many2one(
        'hr.job',
        domain="[('department_id', '=', department_id), ('no_of_recruitment', '>', 0)]"
    )

    # @api.onchange('department_id', 'job_id', 'state')
    # def _onchange_department_id_job_id(self):
    #     if self.employee_id:
    #         self.employee_id._onchange_contract_ids_department_id_job_id()
    #
    @api.onchange('department_id', 'job_id')
    def _onchange_department_job(self):
        if self.employee_id:
            open_contract = self.employee_id.contract_ids.filtered(lambda c: c.state == 'open')
            if open_contract:
                open_contract.department_id = self.department_id
                open_contract.job_id = self.job_id

    def notification_contract_expiration(self):
        date_today = fields.Date.from_string(fields.Date.today())
        for company in self.env['res.company'].search([]):
            outdated_days = fields.Date.to_string(date_today + relativedelta(days=company.alert_contract))
            nearly_expired_contracts = self.search([('state', '=', 'open'), ('date_end', '<', outdated_days)])

            template = self.env.ref('l10n_hn_hr_contract.email_template_notification_contract')

            for contract in nearly_expired_contracts:
                if contract.employee_id.coach_id:
                    coach = contract.employee_id.coach_id
                    if coach.work_email:
                        template.write({'email_to': coach.work_email})
                        template.send_mail(contract.id, force_send=True)

    def notification_contract_expiration_one_day(self):
        date_today = fields.Date.from_string(fields.Date.today())
        for company in self.env['res.company'].search([]):
            outdated_days = fields.Date.to_string(date_today + relativedelta(days=1))
            nearly_expired_contracts = self.search([('state', '=', 'open'), ('date_end', '<', outdated_days)])

            template = self.env.ref('l10n_hn_hr_contract.email_template_notification_contract')

            for contract in nearly_expired_contracts:
                if contract.employee_id.coach_id:
                    coach = contract.employee_id.coach_id
                    if coach.work_email:
                        template.write({'email_to': coach.work_email})
                        template.send_mail(contract.id, force_send=True)


class Position(models.Model):
    _name = 'hr.position'
    _description = 'Puesto'
    _order = 'code'

    code = fields.Char(string='Codigo', copy=False)
    name = fields.Char(string='Titulo del puesto', required=True)


class Job(models.Model):
    _inherit = "hr.job"

    name = fields.Char(translate=False)
    position_id = fields.Many2one('hr.position', string='Puesto',
                                  required=False)
    code = fields.Char(string='Código', copy=False)

    @api.onchange('code')
    def _onchange_code(self):
        if self.code:
            rec = self.env['hr.position'].search([('code', '=', self.code)])
            if rec:
                self.position_id = rec.id
            else:
                return {
                    'warning': {
                        'title': 'Código Incorrecto',
                        'message': 'El código %s no existe' % self.code
                    }
                }

    @api.onchange('position_id')
    def _onchange_position_id(self):
        if self.position_id:
            self.name = self.position_id.name
            self.code = self.position_id.code


