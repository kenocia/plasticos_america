# -*- coding: utf-8 -*-
import time
import babel
from odoo import models, Command, fields, api, tools, _
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    loan_line_id = fields.Many2one('hr.loan.line', string="Loan Installment",
                                   help="Loan installment")


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('employee_id', 'contract_id', 'struct_id', 'date_from', 'date_to',
                 'struct_id')
    def _compute_input_line_ids(self):
        super(HrPayslip, self)._compute_input_line_ids()
        print('Input line IDs')
        input_line_vals = []
        attachment_types = self._get_attachment_types_load()
        attachment_type_ids = [f.id for f in attachment_types.values()]
        lines_to_remove = self.input_line_ids.filtered(
            lambda x: x.input_type_id.id in attachment_type_ids)
        input_line_vals = [Command.unlink(line.id) for line in lines_to_remove]
        print('Lineas eliminadas: ', lines_to_remove)
        for payslip in self:
            # structure_13avo = self.env.ref('l10n_hn_hr_payroll.structure_type_13avo')
            # structure_14avo = self.env.ref('l10n_hn_hr_payroll.structure_type_14avo')
            # print(payslip.struct_id.id)
            # if payslip.struct_id.id not in (structure_13avo.id, structure_14avo.id):
            print('Entro a Calculo de Linea')
            emp_id = payslip.employee_id
            if payslip.employee_id:
                lon_obj = payslip.env['hr.loan'].search(
                    [('employee_id', '=', emp_id.id), ('state', '=', 'approve')])

                for loan in lon_obj:
                    for loan_line in loan.loan_lines:
                        if payslip.date_from <= loan_line.date <= payslip.date_to and not loan_line.paid:
                            print('Entro a la validacion')
                            input_type = payslip.env.ref(
                                'l10n_hn_loan.payslip_input_type_loan')
                            input_line_vals.append(Command.create({
                                'name': loan.name,
                                'amount': loan_line.amount,
                                'input_type_id': input_type.id,
                                'loan_line_id': loan_line.id
                            }))
                    payslip.update({'input_line_ids': input_line_vals})
            else:
                payslip.update({'input_line_ids': input_line_vals})

    def action_payslip_done(self):
        for payslip in self:
            for line in payslip.input_line_ids:
                if line.loan_line_id:
                    line.loan_line_id.paid = True
                    line.loan_line_id.payslip_id = payslip.id
                    line.loan_line_id.loan_id._compute_loan_amount()
        return super(HrPayslip, self).action_payslip_done()

    def compute_paid_loan(self):
        for payslip in self:
            for line in payslip.input_line_ids:
                if line.loan_line_id:
                    line.loan_line_id.paid = True
                    line.loan_line_id.payslip_id = payslip.id
                    line.loan_line_id.loan_id._compute_loan_amount()

    @api.model
    def _get_attachment_types_load(self):
        return {
            'load': self.env.ref('l10n_hn_loan.payslip_input_type_loan'),
        }
