# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import random

from collections import defaultdict, Counter
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv.expression import AND
from odoo.tools import float_round, date_utils, convert_file, html2plaintext, \
    is_html_empty, format_amount
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Sirve para distinguir si un payslip ya ha sido confirmado previamente y evitar registrar cuotas aplicadas por error
    benefit_deduction_apply = fields.Boolean(string="Beneficios y deducciones aplicadas",
                                             default=False, tracking=True, copy=False)

    def send_payment_voucher_email_edi(self):
        """ Envia el voucher de pago por correo electrónico."""
        mail_template = self.env.ref('payroll_hn.email_template_payment_voucher',
                                     raise_if_not_found=False)

        ctx = {
            'default_model': 'hr.payslip',
            'default_res_ids': self.ids,
            'default_template_id': mail_template.id if mail_template else None,
            'force_email': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def send_payment_voucher_email(self):
        """ Envia el voucher de pago por correo electrónico."""
        self.ensure_one()
        subject = 'Voucher de pago'
        # Obtén la acción del reporte
        classic_report = self.env.ref('hr_payroll.action_report_payslip')

        # Genera el PDF utilizando el reporte clásico y el ID de la nómina
        pdf_content, dummy = classic_report.sudo().with_context(
            lang=self.employee_id.lang)._render_qweb_pdf([self.id])

        name = str(self.name) + '_.pdf'
        # Adjuntar el PDF al correo
        attachment_data = {
            'name': name,
            'type': 'binary',
            'raw': pdf_content,
            'res_model': self._name,
            'res_id': self.id
        }

        message_body = self._get_mail_template()

        template_obj = self.env['mail.mail'].sudo()
        template_data = {
            'subject': subject,
            'body_html': message_body,
            'email_to': self.employee_id.work_email or self.employee_id.private_email,
            'attachment_ids': [(0, 0, attachment_data)]
        }
        template_id = template_obj.create(template_data)
        template_id.send()

    def _get_mail_template(self):
        """ Obtiene la plantilla de correo para enviar el voucher de pago."""
        self.ensure_one()
        message_body = f"""
        <table border="0" cellpadding="0" cellspacing="0" style="padding-top: 16px; background-color: #F1F1F1; font-family:Verdana, Arial,sans-serif; color: #454748; width: 100%; border-collapse:separate;">
            <tbody>
                <tr>
                    <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="590" style="padding: 16px; background-color: white; color: #454748; border-collapse:separate;">
                        <tbody>
                        <tr>
                            <td align="center" style="min-width: 590px;">
                                <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate;">
                                    <tbody>
                                        <tr>
                                            <td valign="middle">
                                                <span style="font-size: 15px; font-weight: bold;">Voucher de pago</span><br/>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="min-width: 590px; margin-top: 20px;">
                                <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate; margin-top: 20px;">
                                    <tbody>
                                    <tr>
                                        <td valign="top">
                                            <div style="font-size: 10px;">
                                                Buen dia {self.employee_id.name},<br/>
                                                Adjunto voucher de pago correspondiente al periodo de {self.date_from.strftime('%d/%m/%Y')} - {self.date_to.strftime('%d/%m/%Y')}.<br/><br/>
                                                Saludos.
                                            </div>
                                            <br/>
                                            <div style="font-size: 9px;">
                                                Este correo fue generado de manera automática por lo que no es necesario que lo conteste.
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="text-align:center;">
                                            <hr width="100%" style="background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0; margin: 16px 0px 16px 0px;">
                                        </td>
                                    </tr>
                                    </tbody>
                                </table>
                            </td>
                        </tr>
                        </tbody>
                    </table>
                    </td>
                </tr>
                <tr>
                    <td align="center" style="min-width: 590px;">
                    <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width: 590px; background-color: #F1F1F1; color: #454748; padding: 8px; border-collapse:separate;">
                        <tbody>
                        <tr>
                            <td style="text-align: center; font-size: 13px;">
                            Con tecnología de <a target="_blank" href="https://www.odoo.com?utm_source=db&amp;utm_medium=portalinvite" style="color: #875A7B;">Odoo</a>
                            </td>
                        </tr>
                        </tbody>
                    </table>
                    </td>
                </tr>
            </tbody>
        </table>
        """
        return message_body

    """ Heredo la función de registrar pago para verificar si algún beneficio o deducción es de periodicidad finita y registrar la cuota aplicada. """

    def action_payslip_paid(self):
        res = super().action_payslip_paid()
        for payslip in self:
            if not payslip.benefit_deduction_apply:
                lines = payslip.line_ids.filtered(
                    lambda x: x.salary_rule_id.benefit_deduction and x.amount != 0)
                for line in lines:
                    rule = payslip.contract_id.benefit_deduction_ids.filtered(lambda
                                                                                  x: x.rule_id.code == line.salary_rule_id.code and x.state == 'progress')
                    if rule and rule.fee_numbers_apply < rule.fee_numbers:
                        rule.fee_numbers_apply += 1
                        if rule.fee_numbers_apply == rule.fee_numbers:
                            rule.write({'state': 'done'})
                        payslip.write({'benefit_deduction_apply': True})
                    self.register_benefit_deduction_history(payslip, rule)
            self.register_ihss_history(payslip)
            self.register_rap_history(payslip)
            self.register_isr_history(payslip)
        return res

    def register_ihss_history(self, payslip):
        history = self.env['hr.hn.ihss.history']
        vals = {
            'contract_id': payslip.contract_id.id,
            'employee_id': payslip.employee_id.id,
            'department_id': payslip.contract_id.department_id.id,
            'job_id': payslip.contract_id.job_id.id,
            'ihss_id': payslip.contract_id.ihss_id.id,
            'payslip_run_id': payslip.payslip_run_id.id,
            'payslip_id': payslip.id,
            'schedule_pay': payslip.contract_id.schedule_pay,
            'amount_ihss': payslip.contract_id.amount_ihss,
            'value_ihss': payslip.contract_id.value_ihss,
            'apply_in_ihss': payslip.contract_id.apply_in_ihss,
            'initial_date': payslip.date_from,
            'end_date': payslip.date_to,
            'salary': payslip.contract_id.wage,
            'montly_salary': payslip.contract_id.montly_salary,
            'salary_pay': payslip.net_wage,
        }
        history.create(vals)

    def register_rap_history(self, payslip):
        history = self.env['hr.hn.rap.history']
        vals = {
            'contract_id': payslip.contract_id.id,
            'employee_id': payslip.employee_id.id,
            'department_id': payslip.contract_id.department_id.id,
            'job_id': payslip.contract_id.job_id.id,
            'rap_id': payslip.contract_id.rap_id.id,
            'payslip_run_id': payslip.payslip_run_id.id,
            'payslip_id': payslip.id,
            'schedule_pay': payslip.contract_id.schedule_pay,
            'amount_rap': payslip.contract_id.amount_rap,
            'value_rap': payslip.contract_id.value_rap,
            'apply_in_rap': payslip.contract_id.apply_in_rap,
            'initial_date': payslip.date_from,
            'end_date': payslip.date_to,
            'salary': payslip.contract_id.wage,
            'montly_salary': payslip.contract_id.montly_salary,
            'salary_pay': payslip.net_wage,
        }
        history.create(vals)

    def register_isr_history(self, payslip):
        history = self.env['hr.hn.isr.history']
        vals = {
            'contract_id': payslip.contract_id.id,
            'employee_id': payslip.employee_id.id,
            'department_id': payslip.contract_id.department_id.id,
            'job_id': payslip.contract_id.job_id.id,
            'isr_id': payslip.contract_id.isr_id.id,
            'payslip_run_id': payslip.payslip_run_id.id,
            'payslip_id': payslip.id,
            'schedule_pay': payslip.contract_id.schedule_pay,
            'amount_isr': payslip.contract_id.amount_isr,
            'value_isr': payslip.contract_id.value_isr,
            'apply_in_isr': payslip.contract_id.apply_in_isr,
            'initial_date': payslip.date_from,
            'end_date': payslip.date_to,
            'salary': payslip.contract_id.wage,
            'montly_salary': payslip.contract_id.montly_salary,
            'salary_pay': payslip.net_wage,
        }
        history.create(vals)

    def register_benefit_deduction_history(self, payslip, rule):
        history = self.env['hr.hn.benefit.deduction.history']
        vals = {
            'contract_id': payslip.contract_id.id,
            'employee_id': payslip.employee_id.id,
            'payslip_run_id': payslip.payslip_run_id.id,
            'payslip_id': payslip.id,
            'schedule_pay': payslip.contract_id.schedule_pay,
            'initial_date': payslip.date_from,
            'end_date': payslip.date_to,
            'salary': payslip.contract_id.wage,
            'montly_salary': payslip.contract_id.montly_salary,
            'salary_pay': payslip.net_wage,
            'category': rule.category,
            'rule_id': rule.rule_id.id,
            'fee_amount': rule.fee_amount,
            'fee_amount_apply': rule.fee_amount_apply,
            'apply_in': rule.apply_in,
            'periodicity': rule.periodicity,
        }
        history.create(vals)