from odoo import fields, models, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

MESES= {'1': 'Enero',
        '2':'Febrero',
        '3':'Marzo',
        '4':'Abril',
        '5':'Mayo',
        '6':'Junio',
        '7':'Julio',
        '8':'Agosto',
        '9':'Septiembre',
        '10':'Octubre',
        '11':'Noviembre',
        '12':'Diciembre'}


class HrPayrollBenefitsMonths(models.Model):
    _name = 'hr.payroll.benefits.months'
    # _description = 'Ultimos Salarios Devengados'
    _rec_name = "benefits_id"

    benefits_id = fields.Many2one('hr.payroll.benefits', 'Prestaciones', required=True, ondelete='cascade')
    date_salary_paid = fields.Date(string='Fecha Pagada', help="Fecha de salario pagado", required=True)
    month = fields.Char(compute='_compute_month', readonly=True, store=True)
    salary = fields.Float("Salario")

    @api.depends('date_salary_paid')
    def _compute_month(self):
        for record in self:
            if record.date_salary_paid:
                record.month = MESES[str(record.date_salary_paid.month)]

