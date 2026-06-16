# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from collections import defaultdict
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.tools.misc import xlsxwriter


class L10nHNBankSummaryWizard(models.TransientModel):
    _name = 'l10n.hn.payroll.summary'
    _description = 'Nómina: Nómina Resumen'
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
    line_ids = fields.One2many('l10n.hn.payroll.summary.line', 'sheet_id', string='Lines', compute='_compute_line_ids',
                               store=True, readonly=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Pay Structure", default=lambda self: self._get_default_struct_id())
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    pdf_attachment_id = fields.Many2one('ir.attachment', 'PDF Attachment', readonly=True)
    payroll_pdf_file = fields.Binary('Monthly Summary PDF', related='pdf_attachment_id.datas', readonly=True)
    payroll_pdf_filename = fields.Char('Pdf Filename', compute="_compute_filename")
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('generated', 'Generado'),
        ],
        default='draft',
        readonly=True,
    )

    @api.depends('date_from', 'date_to')
    def _compute_filename(self):
        for record in self:
            date_from = record.date_from if record.date_from else date.today()
            date_to = record.date_to if record.date_to else date.today()
            start_period_str = format_date(self.env, date_from, date_format="Y MMM dd", lang_code='en_US').upper()
            end_period_str = format_date(self.env, date_to, date_format="Y MMM dd", lang_code='en_US').upper()
            record.payroll_pdf_filename = "PTL%s-%s-%s-Resumen.pdf" % (start_period_str, end_period_str, self.struct_id.name )

    @api.depends('date_to', 'date_from', 'company_id', 'struct_id')
    def _compute_line_ids(self):
        for sheet in self:
            all_payslips = self.env['hr.payslip'].search([
                ('state', 'in', ['done', 'paid']),
                ('company_id', '=', sheet.company_id.id),
                ('date_from', '>=', sheet.date_from),
                ('date_to', '<=', sheet.date_to),
                ('struct_id', '=', self.struct_id.id),
            ])
            sheet.update({
                'line_ids': [(5, 0, 0)] + [
                    (0, 0, {'employee_id': employee.id}) for employee in all_payslips.employee_id
                ]
            })

    @api.depends('payroll_pdf_filename')
    def _compute_display_name(self):
        for sheet in self:
            sheet.display_name = sheet.payroll_pdf_filename.replace('.pdf', '').upper()

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

    def _get_line_values_payroll(self):
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
            total_amount_basic = 0
            total_salary = 0
            total_extra_hours = 0
            total_amount_extra_hours = 0
            total_amount_alw = 0
            total_amount_gross = 0
            total_amount_ded_IHSS = 0
            total_amount_ded_RAP = 0
            total_amount_ded_ISR = 0
            total_amount_ded_other = 0
            total_amount_ded_all = 0
            total_amount_net = 0

            employees_data = []
            for employee in employee_payslips:
                line = self.line_ids.filtered(lambda l: l.employee_id == employee)
                payslips = employee_payslips[employee]
                code_name = line.employee_id.registration_number + '-' + line.employee_id.name.upper()
                mapped_total = {
                    code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                    for code in rules.mapped('code')}
                amount_salary = employee.contract_id.wage
                amount_basic = mapped_total['BASIC']
                amount_extra_hours = mapped_total['OVERTIME']
                amount_gross = mapped_total['GROSS']
                amount_alw = abs(mapped_total['CHILD_SUPPORT']) + abs(mapped_total['ASSIG_SALARY']) + abs(
                    mapped_total['ATTACH_SALARY'])
                amount_ded_IHSS = abs(mapped_total['IHSS_RAS']) + abs(mapped_total['IHSS_RPS'])
                amount_ded_RAP = abs(mapped_total['RAP'])
                amount_ded_ISR = 0
                amount_ded_other = 0
                amount_ded_all = amount_ded_IHSS + amount_ded_RAP + amount_ded_ISR + amount_ded_other
                amount_net = abs(mapped_total['NET'])
                date_hired = line.employee_id.date_hired
                employees_data.append({
                    'name': code_name or '',
                    'date_hired': date_hired.strftime('%m/%d/%Y'),
                    'job_position': line.employee_id.job_title,
                    'amount_salary': amount_salary,
                    'worked_days': sum([line.number_of_days for p in payslips for line in p.worked_days_line_ids if
                                        not line.is_credit_time and line.code in ('WORK100', 'DAY_FREE')]),
                    'extra_hours': sum([line.number_of_hours for p in payslips for line in p.worked_days_line_ids if
                                        not line.is_credit_time and line.code in ('OVERTIME') and (p.overtime_hours_for_all or not p.employee_id.has_not_over_time)]),
                    'amount_basic': amount_basic,
                    'amount_extra_hours': amount_extra_hours,
                    'amount_alw': amount_alw,
                    'amount_gross': amount_gross,
                    'amount_ded_IHSS': amount_ded_IHSS,
                    'amount_ded_RAP': amount_ded_RAP,
                    'amount_ded_ISR': amount_ded_ISR,
                    'amount_ded_other': amount_ded_other,
                    'amount_ded_all': amount_ded_all,
                    'period_start': self.date_from.strftime('%m/%d/%Y'),
                    'period_end': self.date_to.strftime('%m/%d/%Y'),
                    'amount_net': amount_net,
                })
                total_amount_basic += amount_basic
                total_extra_hours += 0
                total_amount_extra_hours += amount_extra_hours
                total_amount_alw += amount_alw
                total_amount_gross += amount_gross
                total_amount_ded_IHSS += amount_ded_IHSS
                total_amount_ded_RAP += amount_ded_RAP
                total_amount_ded_ISR += 0
                total_amount_ded_other += 0
                total_amount_ded_all += amount_ded_all
                total_amount_net += amount_net

            total_data = {
                'total_amount_basic': total_amount_basic,
                'total_extra_hours': total_extra_hours,
                'total_amount_extra_hours': total_amount_extra_hours,
                'total_amount_alw': total_amount_alw,
                'total_amount_gross': total_amount_gross,
                'total_amount_ded_IHSS': total_amount_ded_IHSS,
                'total_amount_ded_RAP': total_amount_ded_RAP,
                'total_amount_ded_ISR': total_amount_ded_ISR,
                'total_amount_ded_other': total_amount_ded_other,
                'total_amount_ded_all': total_amount_ded_all,
                'total_amount_net': total_amount_net,
            }
            return {'employees_data': employees_data, 'total_data': total_data, 'total_payslip': total_payslip,
                    'company': self.company_id.name, 'pago': self.struct_id.name.upper()}
        else:
            return {'employees_data': [], 'total_data': [], 'total_payslip': 0, 'company': "", 'pago': ""}

    def _generate_attachment(self):
        """ Function to create the PDF file.
            :param: values_dict All information about the partner
            :return: A PDF file
        """
        self.ensure_one()
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()

        statement_report_action = self.env.ref('l10n_hn_hr_payroll.action_report_payroll_summary')
        report_title = " Resumen nomina.pdf"
        for statement in self:
            statement_report = statement_report_action.sudo()
            content = ir_actions_report_sudo._render_qweb_pdf(statement_report)
            filename = _("%s %s " + report_title, statement.date_from.strftime("%d %B %Y"), statement.date_to.strftime("%d %B %Y"))
            statement.payroll_pdf_filename = filename
            # statement.payroll_pdf_file = base64.encodebytes(content)
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'raw': content,
                'mimetype': 'application/pdf',
                'res_model': statement._name,
                'res_id': statement.id,
            })
            statement.pdf_attachment_id = attachment

    def get_payslip(self):
        line_values = self._get_line_values_payroll()
        name_struct_choice = self.struct_id.name if self.struct_id else 'MENSUAL'
        date_from = self.date_from if self.date_from else date.today()
        period_str_month_year = format_date(self.env, date_from, date_format="MMM Y", lang_code='en_US').upper()
        start_str_date = format_date(self.env, date_from, date_format="dd/MM/YYYY", lang_code='en_US').upper()
        date_to = self.date_to if self.date_to else date.today()
        end_str_date = format_date(self.env, date_to, date_format="dd/MM/YYYY", lang_code='en_US').upper()
        title_format = "PTL%s-%s-%s Del:%s AL: %s" % (str(self.date_from.year), name_struct_choice.upper(), period_str_month_year, start_str_date, end_str_date)

        line_values.update({'title_format': title_format})
        return line_values

    def action_print_payslip(self):
        self.ensure_one()
        self._generate_attachment()
        self.state = 'generated'
        return {
            'type': 'ir.actions.act_url',
            'name': _("Resuen de nómina PDF Bajar"),
            'url': f"/web/content/{self.pdf_attachment_id.id}?download=true",
            'close': True,
            "target": "new",
        }

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft',
            'pdf_attachment_id': False,
            'payroll_pdf_filename': '',
            'payroll_pdf_file': b'',
            'payroll_pdf_filename': ''
        })

    def compute_sheet(self):
        self.action_reset_to_draft()
        self._generate_attachment()

    def _validate_form(self):
        self.ensure_one()
        if self.state != 'generated':
            self.write({
                'state': 'generated',
            })


class L10nBankSummaryLine(models.TransientModel):
    _name = 'l10n.hn.payroll.summary.line'
    _description = 'Monthly summary line'

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id, sheet_id)', 'An employee can only have one line per sheet'),
    ]

    employee_id = fields.Many2one('hr.employee', required=True)
    sheet_id = fields.Many2one('l10n.hn.payroll.summary', required=True, ondelete='cascade')