# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError


class HrQuitRequest(models.Model):
    _name = 'hr.quit.request'
    _description = "Solicitud de renuncia"

    name = fields.Char(string="Solicitud de renuncia", default="/", readonly=True,
                       help="Nombre de solicitud de renuncia")
    quit_date = fields.Date(string="Fecha de solicitud", default=fields.Date.today(), help="Date")
    expected_date = fields.Date(string="Fecha cierre prevista", compute='_compute_expected_date' , store=True)
    accepted_date = fields.Date(string="Fecha de aceptada", default=fields.Date.today(), help="Date")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, help="Employee")
    department_id = fields.Many2one('hr.department', related="employee_id.department_id", readonly=True,
                                    string="Department", help="Employee")
    company_id = fields.Many2one('res.company', 'Company', readonly=True, help="Company",
                                 default=lambda self: self.env.user.company_id)
    job_position = fields.Many2one('hr.job', related="employee_id.job_id", readonly=True, string="Job Position",
                                   help="Job position")
    penalty_to_be_applied = fields.Float(string="Multa a aplicar")

    state = fields.Selection([
        ('draft', _('Draft')),
        ('open', _('Process')),
        ('refuse', _('Refused')),
        ('cancel', _('Canceled')),
        ('accepted', _('Accepted')),
    ], string="State", default='draft', tracking=True, copy=False, )

    def action_refuse(self):
        return self.write({'state': 'refuse'})

    def action_open(self):
        self.write({'state': 'open'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_accepted(self):
        self.write({'state': 'accepted'})

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].get('hr.quit.request.seq') or ' '
        res = super(HrQuitRequest, self).create(values)
        return res

    @api.depends('quit_date')
    def _compute_expected_date(self):
        for rec in self:
            if rec.quit_date:
                rec.expected_date = rec.quit_date + relativedelta(days=rec.employee_id.previous_days_to_resign)

