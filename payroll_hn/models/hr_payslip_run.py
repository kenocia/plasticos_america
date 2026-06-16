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
import xlsxwriter
import tempfile
import io

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    txt_file = fields.Binary(string='Archivo TXT', readonly=True)
    txt_filename = fields.Char(string='Nombre del archivo TXT')

    def generate_txt_file(self):
        """Genera un archivo TXT con información bancaria de los empleados"""
        self.ensure_one()
        
        # Obtener los payslips del lote
        payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', self.id)])
        
        # Ordenar los payslips alfabéticamente por el nombre del empleado
        payslips = payslips.sorted(key=lambda p: p.employee_id.name)
        
        # Generar el contenido del archivo TXT
        lines = []
        for payslip in payslips:
            # Obtener los datos
            acc_number = payslip.employee_id.bank_account_id.acc_number if payslip.employee_id.bank_account_id else ''
            net_wage = payslip.net_wage
            identification_id = payslip.employee_id.identification_id or ''
            employee_name = payslip.employee_id.name or ''
            
            # Crear la línea con el formato: acc_number|net_wage|identification_id|name
            line = f"{acc_number}|{net_wage}|{identification_id}|{employee_name}"
            lines.append(line)
        
        # Unir todas las líneas con salto de línea
        txt_content = '\n'.join(lines)
        
        # Codificar el contenido en base64
        txt_file = base64.b64encode(txt_content.encode('utf-8'))
        
        # Guardar el archivo en el registro
        self.write({
            'txt_file': txt_file,
            'txt_filename': f'pago_nomina_{self.name}.txt'
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Archivo TXT generado',
                'message': 'El archivo TXT ha sido generado correctamente.',
                'type': 'success',
            }
        }

    def generate_xlsx_file(self, lot_text):
        # Crear un archivo en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Formato numérico con 2 decimales
        num_format = workbook.add_format({'num_format': '0.00'})

        # Obtener los payslips
        payslips = self.env['hr.payslip'].search([('payslip_run_id.name', '=', lot_text)])

        # Ordenar los payslips alfabéticamente por el nombre del empleado
        payslips = payslips.sorted(key=lambda p: p.employee_id.name)

        # Definir encabezados
        benefits = []
        benefits_name = []
        deductions = []
        deductions_name = []

        for payslip in payslips:
            benefit_lines = payslip.line_ids.filtered(
                lambda x: x.amount != 0 and x.category_id.category == 'ALW')
            for line in benefit_lines:
                if line.salary_rule_id not in benefits:
                    benefits.append(line.salary_rule_id)
                    benefits_name.append(line.salary_rule_id.name)

            deduction_lines = payslip.line_ids.filtered(
                lambda x: x.amount != 0 and x.category_id.category == 'DED')
            for line in deduction_lines:
                if line.salary_rule_id not in deductions:
                    deductions.append(line.salary_rule_id)
                    deductions_name.append(line.salary_rule_id.name)

        # Escribir encabezados en la primera fila
        row = 0
        col = 0
        worksheet.write(row, col, 'No.')
        col += 1
        worksheet.write(row, col, 'Nombre y apellidos')
        col += 1
        worksheet.write(row, col, 'Sucursal')
        col += 1
        worksheet.write(row, col, 'Salario base')
        col += 1
        for benefit in benefits_name:
            worksheet.write(row, col, benefit)
            col += 1
        worksheet.write(row, col, 'Salario bruto')
        col += 1
        for deduction in deductions_name:
            worksheet.write(row, col, deduction)
            col += 1
        worksheet.write(row, col, 'Salario Neto')

        # Escribir datos de los empleados
        row = 1
        count = 0
        totals_benefits = [0] * len(benefits)
        totals_deductions = [0] * len(deductions)

        total_salary_basic = 0
        total_salary_gross = 0
        total_salary_net = 0

        for payslip in payslips:
            payslip_line = self.env['hr.payslip.line'].search(
                [('category_id.category', '=', 'BASIC'), ('slip_id', '=', payslip.id),
                 ('contract_id', '=', payslip.contract_id.id)], limit=1)

            rules_benefits = []
            rules_deductions = []
            total_deductions = 0
            total_benefits = 0

            for rule_index, rule in enumerate(benefits):
                line = payslip.line_ids.filtered(lambda x: x.salary_rule_id.id == rule.id)

                if line:
                    amount = line.amount
                else:
                    amount = 0

                total_benefits += amount
                rules_benefits.append(amount)
                totals_benefits[rule_index] += amount  # Sumar al total de beneficios

            for rule_index, rule in enumerate(deductions):
                line = payslip.line_ids.filtered(lambda x: x.salary_rule_id.id == rule.id)

                if line:
                    amount = line.amount
                else:
                    amount = 0

                total_deductions += amount
                rules_deductions.append(amount)
                totals_deductions[rule_index] += amount  # Sumar al total de deducciones

            salary_gross = payslip_line.total + total_benefits
            salary_net = salary_gross - total_deductions

            total_salary_basic += payslip_line.total
            total_salary_gross += salary_gross
            total_salary_net += salary_net

            col = 0
            count += 1
            worksheet.write(row, col, count)
            col += 1
            worksheet.write(row, col, payslip.employee_id.name)
            col += 1
            worksheet.write_number(row, col, payslip_line.total, num_format)
            col += 1
            for amount in rules_benefits:
                worksheet.write_number(row, col, amount, num_format)
                col += 1
            worksheet.write_number(row, col, salary_gross, num_format)
            col += 1
            for amount in rules_deductions:
                worksheet.write_number(row, col, amount, num_format)
                col += 1
            worksheet.write_number(row, col, salary_net, num_format)
            row += 1

        # Escribir totales en la última fila
        col = 0
        worksheet.write(row, col, 'Totales')
        col += 2
        worksheet.write_number(row, col, total_salary_basic, num_format)
        col += 1
        for total in totals_benefits:
            worksheet.write_number(row, col, total, num_format)
            col += 1
        worksheet.write_number(row, col, total_salary_gross, num_format)
        col += 1
        for total in totals_deductions:
            worksheet.write_number(row, col, total, num_format)
            col += 1
        worksheet.write_number(row, col, total_salary_net, num_format)

        workbook.close()
        output.seek(0)
        return output.read()

    def send_payment_voucher_email(self):
        self.ensure_one()
        payslips = self.env['hr.payslip'].search([('payslip_run_id', '=', self.id)])
        for payslip in payslips:
            subject = 'Voucher de pago'
            # Obtén la acción del reporte
            classic_report = self.env.ref('hr_payroll.action_report_payslip')

            # Genera el PDF utilizando el reporte clásico y el ID de la nómina
            pdf_content, dummy = classic_report.sudo().with_context(
                lang=payslip.employee_id.lang)._render_qweb_pdf('hr_payroll.action_report_payslip', res_ids=[payslip.id])

            name = str(payslip.name) + '_.pdf'
            # Adjuntar el PDF al correo
            attachment_data = {
                'name': name,
                'type': 'binary',
                'raw': pdf_content,
                'res_model': payslip._name,
                'res_id': payslip.id
            }

            message_body = self._get_mail_template(payslip.employee_id.name)

            template_obj = self.env['mail.mail'].sudo()
            template_data = {
                'subject': subject,
                'body_html': message_body,
                'email_to': payslip.employee_id.work_email or payslip.employee_id.private_email,
                'attachment_ids': [(0, 0, attachment_data)]
            }
            template_id = template_obj.create(template_data)
            template_obj.send(template_id)
            template_id.send()

    def _get_mail_template(self, employee):
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
                                                Buen dia {employee},<br/>
                                                Adjunto voucher de pago correspondiente al periodo de {self.date_start.strftime('%d/%m/%Y')} - {self.date_end.strftime('%d/%m/%Y')}.<br/><br/>
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

    def action_validate(self):
        """Sobrescribir para vincular beneficios/deducciones cuando se pague"""
        result = super().action_validate()
        # Vincular siempre después de validar, independientemente del estado
        self._link_benefit_deduction_lines()
        return result

    def action_payslip_paid(self):
        """Sobrescribir para vincular beneficios/deducciones cuando se pague"""
        result = super().action_payslip_paid()
        # Vincular también cuando se marque como pagado
        self._link_benefit_deduction_lines()
        return result

    def action_cancel(self):
        """Sobrescribir para desvincular beneficios/deducciones cuando se cancele"""
        result = super().action_cancel()
        self._unlink_benefit_deduction_lines()
        return result

    def _link_benefit_deduction_lines(self):
        """Vincular líneas de beneficios/deducciones que coincidan con el rango de fechas"""
        if not self.date_start or not self.date_end:
            _logger.warning(f"Lote {self.name}: No se pueden vincular líneas - fechas no definidas")
            return

        _logger.info(f"Vinculando líneas para lote {self.name} (fechas: {self.date_start} - {self.date_end})")

        # Buscar líneas que coincidan con el rango de fechas
        # Primero buscar las asignaciones que coincidan con el rango de fechas
        assignments = self.env['hr.hn.assign.benefit.deduction'].search([
            ('start_date', '>=', self.date_start),
            ('start_date', '<=', self.date_end),
            ('state', '=', 'done')  # Solo asignaciones aplicadas
        ])
        
        # Luego buscar las líneas de esas asignaciones
        lines = self.env['hr.hn.assign.benefit.deduction.line'].search([
            ('assign_id', 'in', assignments.ids)
        ])

        _logger.info(f"Encontradas {len(assignments)} asignaciones y {len(lines)} líneas para vincular")

        # Vincular las líneas encontradas con este lote
        linked_count = 0
        for line in lines:
            if self.id not in line.payslip_batch_ids.ids:
                line.payslip_batch_ids = [(4, self.id)]
                linked_count += 1
                _logger.info(f"Vinculada línea {line.id} del empleado {line.employee_id.name}")

        # Forzar el recálculo del estado de pago
        if lines:
            lines._compute_payment_status()

        _logger.info(f"Total de líneas vinculadas: {linked_count}")

    def test_link_benefit_deduction_lines(self):
        """Método de prueba para vincular líneas manualmente"""
        self.ensure_one()
        _logger.info(f"Iniciando prueba de vinculación para lote {self.name}")
        self._link_benefit_deduction_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Vinculación completada',
                'message': f'Se ejecutó la vinculación para el lote {self.name}. Revisa los logs para más detalles.',
                'type': 'success',
            }
        }

    def _unlink_benefit_deduction_lines(self):
        """Desvincular líneas de beneficios/deducciones del lote cancelado"""
        # Buscar líneas vinculadas a este lote
        lines = self.env['hr.hn.assign.benefit.deduction.line'].search([
            ('payslip_batch_ids', 'in', [self.id])
        ])

        # Desvincular las líneas del lote cancelado
        for line in lines:
            line.payslip_batch_ids = [(3, self.id)]

        # Forzar el recálculo del estado de pago
        if lines:
            lines._compute_payment_status()