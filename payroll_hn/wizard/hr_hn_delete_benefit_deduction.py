from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import datetime, timedelta, time
import io
#import openpyxl
import base64

class HrHnDeleteBenefitDeduction(models.TransientModel):
    _name = 'hr.hn.delete.benefit.deduction'
    _description = "Asignación de beneficios y deduicciones"
    _rec_name = "rule_id"
    _check_company_auto = True

    company_id = fields.Many2one(string="Compañía", comodel_name="res.company", required=True, default=lambda self: self.env.company)
    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio')], required=True)
    rule_id = fields.Many2one(string="Regla", comodel_name="hr.salary.rule", required=True)
    state = fields.Selection(string=_('State'), selection=[('draft', _('Borrador')),('done', _('Pausado')),], default='draft',)
    line_ids = fields.One2many(string="Lineas de asignación de beneficios y deducciones", comodel_name="hr.hn.delete.benefit.deduction.line", inverse_name="delete_id")

    def get_employees(self):
        delete_line = self.env['hr.hn.delete.benefit.deduction.line']
        delete_line.search([('delete_id','=',self.id)])

        benefits_deductions = self.env['hr.hn.benefit.deduction'].search([
            ('rule_id','=',self.rule_id.id),
            ('contract_id.company_id','=',self.company_id.id)
        ])
        values = []

        if len(benefits_deductions) > 0:
            for bd in benefits_deductions:
                vals = {
                    'employee_id': bd.contract_id.employee_id.id,
                    'contract_id': bd.contract_id.id,
                    'amount': bd.fee_amount_apply,
                    'line_id': bd.id,
                    'delete_id': self.id,
                }
                values.append(vals)
            delete_line.create(values)
    
    def action_done(self):
        self.write({'state': 'done'})

    def action_delete(self):
        for line in self.line_ids:
            line.line_id.unlink()
        self.action_done()


class HrHnDeleteBenefitDeductionLine(models.TransientModel):
    _name = 'hr.hn.delete.benefit.deduction.line'
    _description = "Lineas de borrar de beneficios y deduicciones"
    _check_company_auto = True

    company_id = fields.Many2one(string="Compañía", comodel_name="res.company", required=True, default=lambda self: self.env.company, related="delete_id.company_id", store=True)
    employee_id = fields.Many2one(string="Empleado", comodel_name="hr.employee", check_company=True)
    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract", check_company=True)
    amount = fields.Float(string="Monto")
    line_id = fields.Many2one(comodel_name="hr.hn.benefit.deduction")
    delete_id = fields.Many2one(string="", comodel_name="hr.hn.delete.benefit.deduction", required=True, ondelete='cascade')