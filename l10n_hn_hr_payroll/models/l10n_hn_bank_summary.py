# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from collections import defaultdict
from datetime import date

import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.tools.misc import xlsxwriter
from odoo.tools.config import config
from pathlib import Path
from datetime import date, datetime, time


class L10nHNBankSummaryModel(models.Model):
    _name = 'l10n.hn.bank.summary'
    _description = 'Nómina: Banco Resumen'
    _order = 'date_from'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id.code != "HN":
            raise UserError(_('You must be logged in a Hondure company to use this feature'))
        return super().default_get(field_list)

    @api.model
    def _get_default_struct_id(self):
        return self.env.ref('l10n_hn_hr_payroll.structure_month', False)

    date_from = fields.Date(
        string='From', readonly=False, required=True)
    date_to = fields.Date(
        string='To', readonly=False, required=True)
    line_ids = fields.One2many('l10n.hn.bank.summary.line', 'sheet_id', string='Lines', compute='_compute_line_ids',
                               store=True, readonly=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Pay Structure", default=lambda self: self._get_default_struct_id())
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    partner_bank_id = fields.Many2one('res.partner.bank',  domain="[('partner_id', '=', company_id)]")
    pdf_attachment_id = fields.Many2one('ir.attachment', 'PDF Attachment', readonly=True)
    bank_pdf_file = fields.Binary('Resumen en PDF', related='pdf_attachment_id.datas', readonly=True)
    bank_pdf_filename = fields.Char('Pdf Filename', compute="_compute_filename")
    txt_attachment_id = fields.Many2one('ir.attachment', 'TXT Attachment', readonly=True)
    bank_txt_file = fields.Binary('Resumen en txt', related='txt_attachment_id.datas', readonly=True)
    bank_txt_filename = fields.Char()
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('send', 'Enviado'),
        ],
        default='draft',
        readonly=True,
    )
    generate_pdf = fields.Boolean()

    @api.depends('date_from', 'date_to')
    def _compute_filename(self):
        for record in self:
            date_from = record.date_from if record.date_from else date.today()
            date_to = record.date_to if record.date_to else date.today()
            start_period_str = format_date(self.env, date_from, date_format="Y MMM dd", lang_code='en_US').upper()
            end_period_str = format_date(self.env, date_to, date_format="Y MMM dd", lang_code='en_US').upper()
            record.bank_pdf_filename = "%s-%s-%s-summary.pdf" % (start_period_str, end_period_str, self.struct_id.name )

    @api.depends('date_to', 'date_from', 'company_id', 'struct_id', 'partner_bank_id')
    def _compute_line_ids(self):
        for sheet in self:
            all_payslips = self.env['hr.payslip'].search([
                ('state', 'in', ['done', 'paid']),
                ('company_id', '=', sheet.company_id.id),
                ('date_from', '>=', sheet.date_from),
                ('date_to', '<=', sheet.date_to),
                ('struct_id', '=', self.struct_id.id),
                ('sent_to_the_bank', '=', False),
                ('employee_id.bank_account_id.bank_id', '=', self.partner_bank_id.bank_id.id),
            ])
            sheet.update({
                'line_ids': [(5, 0, 0)] + [
                    (0, 0, {'employee_id': employee.id}) for employee in all_payslips.employee_id
                ]
            })

    @api.depends('bank_pdf_filename')
    def _compute_display_name(self):
        for sheet in self:
            sheet.display_name = sheet.bank_pdf_filename.replace('.pdf', '').upper()

    def _get_valid_payslips(self):
        default_struct_id = self.struct_id if self.struct_id else self.env.ref('l10n_hn_hr_payroll.structure_month')
        domain = [
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('employee_id', 'in', self.line_ids.employee_id.ids),
            ('struct_id', '=', default_struct_id.id),
        ]
        payslips = self.env['hr.payslip'].search(domain)
        if not payslips:
            raise UserError(_("There is no paid or done payslips over the selected period."))
        return payslips

    def _get_line_values_bank(self):
        self.ensure_one()
        all_payslips = self._get_valid_payslips()

        all_employees = all_payslips.employee_id

        employee_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips:
            employee_payslips[payslip.employee_id] |= payslip

        rules = self.env['hr.payroll.structure'].search([
            # ('country_id', '=', self.env.ref('base.hn').id)
        ]).rule_ids.sorted(lambda r: r.code)

        monthly_pay = self.env.ref('l10n_hn_hr_payroll.structure_month')
        biweekly_pay = self.env.ref('l10n_hn_hr_payroll.structure_biweekly')
        weekly_pay = self.env.ref('l10n_hn_hr_payroll.structure_weekly')

        structures = monthly_pay + biweekly_pay + weekly_pay
        if self.struct_id in structures:
            all_line_values = all_payslips._get_line_values(rules.mapped('code'), vals_list=['total', 'quantity'])
            total_payslip = employee_payslips.__len__()
            total_amount_net = 0

            employees_data = []
            for employee in employee_payslips:
                line = self.line_ids.filtered(lambda l: l.employee_id == employee)
                payslips = employee_payslips[employee]

                mapped_total = {
                    code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                    for code in rules.mapped('code')}

                amount_net = abs(mapped_total['NET'])
                if line.employee_id.identification_id and line.employee_id.bank_account_id.sanitized_acc_number:
                    acc_number = line.employee_id.bank_account_id.sanitized_acc_number
                else:
                    acc_number = ''
                if line.employee_id.has_savings:
                    type_acc = 'CA'
                else:
                    type_acc = 'CC'
                employees_data.append({
                    'member_account': acc_number,
                    'name': line.employee_id.name.upper() or '',
                    'period_start': self.date_from.strftime('%m/%d/%Y'),
                    'period_end': self.date_to.strftime('%m/%d/%Y'),
                    'amount_net': amount_net,
                    'type': "0",
                    'type_acc': type_acc,
                })
                total_amount_net += amount_net
            if self.generate_pdf:
                total_data = {
                    'total_amount_net': total_amount_net,
                }
            else:
                total_data = {
                    'total_amount_net': total_amount_net,
                    'total_payslip': total_payslip,
                }
            return {'employees_data': employees_data, 'total_data': total_data}
        else:
            return {'employees_data': [], 'total_data': []}

    def _generate_attachment(self):
        """ Function to create the PDF file.
            :param: values_dict All information about the partner
            :return: A PDF file
        """
        self.ensure_one()
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()

        statement_report_action = self.env.ref('l10n_hn_hr_payroll.action_report_bank_summary')
        report_title = " Bank Summary.pdf"
        for statement in self:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(
                statement_report,
                res_ids=statement.ids,
                data={'company': statement.company_id}
            )
            filename = _("%s %s " + report_title,
                         statement.date_from.strftime("%d %B %Y"),
                         statement.date_to.strftime("%d %B %Y"))
            statement.bank_pdf_filename = filename

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'raw': base64.b64encode(content),
                'mimetype': 'application/pdf',
                'res_model': statement._name,
                'res_id': statement.id,
            })
            statement.pdf_attachment_id = attachment

    def _generate_attachment_txt(self):
        """ Function to create the TXT file.
            :param: values_dict All information about the partner
            :return: A TXT file
        """
        self.ensure_one()
        line_values = self.get_payslip()
        _date = ''.join(str(self.date_from).split('-'))
        _file = "Planilla para banco{}.txt".format(_date)
        data_dir = config['data_dir']
        file_camino = Path(data_dir) / _file
        # print(file_name)
        file_name = _file
        file = open(file_camino, 'w', encoding='ISO-8859-1')
        file.write("TRANSBNKEL")  # primera linea
        file.write("\r")  # Cambio de linea
        file.write(self.partner_bank_id.acc_number)
        file.write("\r")
        date_now = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        file.write(date_now)
        file.write("\r")
        file.write("\r")
        cnt = str(line_values['total_data']['total_payslip'])
        total_amount = str(line_values['total_data']['total_amount_net'])
        cant_amount = cnt + ':' + str(total_amount)
        file.write(cant_amount)
        file.write("\r")
        #Consecutivo
        if self.partner_bank_id.bank_id and self.partner_bank_id.bank_id.bank_sequence:
            code_sequence = self.partner_bank_id.bank_id.bank_sequence.code
            bank_sequence =  self.env['ir.sequence'].next_by_code(code_sequence)
        else:
            raise ValueError(
                "Debe seleccionar un banco y este tener asignada la secuencia"
            )
        file.write(bank_sequence)
        file.write("\r")
        file.write("< Inicio >")
        file.write("\r")
        consecutivo = 1
        for payslip in line_values['employees_data']:
            file.write(str(consecutivo).zfill(6).ljust(6))
            file.write(("2").zfill(3))
            file.write(("1").zfill(1).ljust(1))
            #columna 2
            #CODIGO SEGUN EMPRESA company_registry o analizar
            if self.company_id.company_registry:
                reg = self.company_id.company_registry
            else:
                reg = " "
            file.write((reg).ljust(10))
            # CODIGO ENTIDAD FINANCIERA DEBITO
            file.write((self.partner_bank_id.bank_id.bic).ljust(3))
            # CODIGO EMPRESA DEBITO
            file.write(("01").ljust(2))
            # *CODIGO AGENCIA DEBITO
            file.write(("0").zfill(3))
            # *CODIGO SUBAPLICACION DEBITO
            file.write(("0").zfill(3))
            # *NUMERO CUENTA DEBITO
            # Este es el número de la cuenta bancaria del empleador desde donde se va a retirar el dinero para pagar la nómina.
            file.write((self.partner_bank_id.acc_number).zfill(12))
            # *CODIGO ENTIDAD FINANCIERA CREDITO
            file.write((self.partner_bank_id.bank_id.bic).ljust(3))
            # *CODIGO EMPRESA CREDITO
            file.write(("01").ljust(2))
            # *CODIGO AGENCIA CREDITO
            file.write(("0").zfill(3))
            # *CODIGO SUBAPLICACION CREDITO
            file.write(("0").zfill(3))
            # *NUMERO CUENTA CREDITO
            # Este es el número de la cuenta bancaria del empleado donde se va a depositar el dinero de la nómina.
            file.write((payslip['member_account']).zfill(12))
            # TIPO CUENTA DESTINO
            file.write(str(payslip['type_acc']))
            # generar 15 espacios en blanco
            file.write((" ").ljust(15))
            #beneficiario
            file.write((payslip['name']).ljust(40))
            #descripción
            file.write((line_values['title_format']).ljust(90))
            #Agencia destino
            file.write(str("0").zfill(3))
            #Monto
            file.write(str(payslip['amount_net']).zfill(14))
            # Situacion
            file.write(str("0").zfill(3))
            file.write("\r")
            consecutivo += 1
        file.write("< Fin >")
        file.close()

        file_data = open(file_camino, 'r', encoding='ISO-8859-1').read()

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'mimetype': 'application/pdf',
            # 'res_id': statement.id,
            'res_id': False,
            'datas': base64.b64encode(file_data.encode('ISO-8859-1')),
        })
        self.bank_txt_filename = file_name
        self.txt_attachment_id = attachment.id

    def get_payslip(self):
        line_values = self._get_line_values_bank()
        name_struct_choice = self.struct_id.name if self.struct_id else 'MENSUAL'
        title_format = "{struct_name}" "{date_format}".format(
            struct_name='PRIMERA QUINCENA ' if name_struct_choice.upper() == 'QUINCENAL' else 'PRIMERA SEMANA ' if name_struct_choice.upper() == 'SEMANAL' else 'DEL MES ' if name_struct_choice.upper() == 'MENSUAL' else name_struct_choice.upper(),
            date_format=self.date_from.strftime("%B %Y").upper()
        )
        line_values.update({'title_format': title_format, 'bank_id': self.partner_bank_id.bank_id})
        return line_values

    def action_print_payslip(self):
        self.ensure_one()
        self.generate_pdf = True
        self._generate_attachment()
        return {
            'type': 'ir.actions.act_url',
            'name': _("Monthly Summary PDF Download"),
            'url': f"/web/content/{self.pdf_attachment_id.id}?download=true",
            'close': True,
            "target": "new",
        }

    def action_print_payslip_txt(self):
        self.ensure_one()
        self.generate_pdf = False
        self._generate_attachment_txt()
        return {
            'type': 'ir.actions.act_url',
            'name': _("Monthly Summary TXT Download"),
            'url': f"/web/content/{self.txt_attachment_id.id}?download=true",
            'close': True,
            "target": "new",
        }

    def action_reset_to_draft(self):
        self.pdf_attachment_id = False
        self.state = 'draft'
        self.write({
            'state': 'draft',
            'pdf_attachment_id': False,
            'bank_pdf_filename': '',
            'bank_pdf_file': b'',
            'bank_pdf_filename': ''
        })

    def compute_sheet(self):
        self.action_reset_to_draft()
        self._generate_attachment()

    def action_send_txt(self):
        self.ensure_one()
        if self.state != 'send':
            all_payslips = self._get_valid_payslips()
            for payslip in all_payslips:
                payslip.sent_to_the_bank = True
            self.write({
                'state': 'send',
            })




class L10nBankSummaryLine(models.Model):
    _name = 'l10n.hn.bank.summary.line'
    _description = 'Monthly summary line'

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id, sheet_id)', 'An employee can only have one line per sheet'),
    ]

    employee_id = fields.Many2one('hr.employee', required=True)
    sheet_id = fields.Many2one('l10n.hn.bank.summary', required=True, ondelete='cascade')