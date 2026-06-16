# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from collections import defaultdict
from datetime import date

from odoo import api, fields, models, _
from odoo.addons.account_online_synchronization.models.account_online import pattern
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.tools.misc import xlsxwriter


class L10nHNMonthlySummaryWizard(models.TransientModel):
    _name = 'l10n.hn.monthly.summary'
    _description = 'Payroll: Monthly Summary'
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
    line_ids = fields.One2many('l10n.hn.monthly.summary.line', 'sheet_id', string='Lines', compute='_compute_line_ids',
                               store=True, readonly=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Pay Structure", default=lambda self: self._get_default_struct_id())
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    pdf_attachment_id = fields.Many2one('ir.attachment', 'PDF Attachment', readonly=True)
    xlsx_attachment_id = fields.Many2one('ir.attachment', 'XLSX Attachment', readonly=True)
    xlsx_file = fields.Binary('XLSX File', related='xlsx_attachment_id.datas', readonly=True)
    xlsx_filename = fields.Char('XLSX Filename', compute="_compute_filename")
    monthly_summary_pdf_file = fields.Binary('Monthly Summary PDF', related='pdf_attachment_id.datas', readonly=True)
    monthly_summary_pdf_filename = fields.Char()
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('generated', 'Generated'),
        ],
        default='draft',
        readonly=True,
    )

    file_type = fields.Selection(
        [
            ('ampliado', 'Ampliado'),
            ('reducido', 'Reducido'),
        ],
        string='Tipo de fichero',
        default='ampliado',
    )

    @api.depends('date_from', 'date_to')
    def _compute_filename(self):
        for record in self:
            date_from = record.date_from if record.date_from else date.today()
            date_to = record.date_to if record.date_to else date.today()
            start_period_str = format_date(self.env, date_from, date_format="Y MMM dd", lang_code='en_US').upper()
            end_period_str = format_date(self.env, date_to, date_format="Y MMM dd", lang_code='en_US').upper()
            record.xlsx_filename = "%s-%s-%s-summary.xlsx" % (start_period_str, end_period_str, self.struct_id.name)

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

    @api.depends('xlsx_filename')
    def _compute_display_name(self):
        for sheet in self:
            sheet.display_name = sheet.xlsx_filename.replace('.xlsx', '').upper()

    def _get_valid_payslips(self):
        default_struct_id = self.struct_id if self.struct_id else self.env.ref('l10n_hn_hr_payroll.structure_month')
        print(default_struct_id)
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

    def _get_line_values(self):
        self.ensure_one()
        all_payslips = self._get_valid_payslips()
        print('GET Values: ', all_payslips)
        all_employees = all_payslips.employee_id

        employee_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips:
            employee_payslips[payslip.employee_id] |= payslip
        print('EMPLEADO PAYSLIP: ', employee_payslips)
        rules = self.env['hr.payroll.structure'].search([
            # ('country_id', '=', self.env.ref('base.hn').id)
        ]).rule_ids.sorted(lambda r: r.code)

        monthly_pay = self.env.ref('l10n_hn_hr_payroll.structure_month')
        biweekly_pay = self.env.ref('l10n_hn_hr_payroll.structure_biweekly')
        weekly_pay = self.env.ref('l10n_hn_hr_payroll.structure_weekly')
        # bonus_pay = self.env.ref('l10n_hn_hr_payroll.structure_bonus')
        # _13_avo_pay = self.env.ref('l10n_hn_hr_payroll.structure_13avo')
        # _14avo_pay = self.env.ref('l10n_hn_hr_payroll.structure_14avo')
        # fini_pay = self.env.ref('l10n_hn_hr_payroll.structure_finiquito')
        # per_pay = self.env.ref('l10n_hn_hr_payroll.structure_perifonista')
        # ani_pay = self.env.ref('l10n_hn_hr_payroll.structure_animador')
        structures = monthly_pay + biweekly_pay + weekly_pay
        print('Estructuras: ', structures)

        if self.struct_id:
            all_line_values = all_payslips._get_line_values(rules.mapped('code'), vals_list=['total', 'quantity'])
            total_amount_gross = 0
            total_amount_net = 0
            total_amount_bonus = 0
            total_amount_prima = 0
            total_amount_alw = 0
            total_amount_ded_IHSS = 0
            total_amount_ded_RAP = 0
            total_amount_tax = 0
            total_amount_comp_patron = 0
            total_amount_comp_patron_rap = 0
            total_amount_comp_PROV_13AVO = 0
            total_amount_comp_PROV_14AVO = 0
            total_amount_alter_bonus = 0
            total_amount_ded_col = 0
            total_amount_basic = 0
            total_amount_comp_patron_infop = 0

            employees_data = []
            print('PAYSLIP #2 : ', employee_payslips)
            for employee in employee_payslips:
                line = self.line_ids.filtered(lambda l: l.employee_id == employee)
                print('LINEA DE EMPLEADOS: ', line)
                payslips = employee_payslips[employee]
                print('PAYSLIP : ', payslips)

                mapped_total = {
                    code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                    for code in rules.mapped('code')}

                amount_basic = mapped_total['INFO01']
                amount_gross = mapped_total['INFO02']
                amount_net = abs(mapped_total['NET'])
                amount_bonus = abs(mapped_total['BONUS']) if 'BONUS' in mapped_total else 0.00
                # amount_prima = abs(mapped_total['DEDUCTION'])
                amount_alw = abs(mapped_total['CHILD_SUPPORT']) + abs(mapped_total['ASSIG_SALARY']) + abs(mapped_total['ATTACH_SALARY'])
                # amount_ded_IHSS = abs(mapped_total['IHSS_RAS']) + abs(mapped_total['IHSS_RPS'])
                amount_ded_IHSS = abs(mapped_total['IHSS'])
                amount_ded_RAP = abs(mapped_total['RAP'])
                amount_tax = 0.00  # abs(mapped_total['FOR_TAX'])
                amount_comp_patron = abs(mapped_total['IHSS_RAS_PAT']) + abs(mapped_total['IHSS_RPS_PAT'])
                amount_comp_patron_rap = abs(mapped_total['RAP_PAT'])
                amount_comp_patron_infop = abs(mapped_total['INFOP_PAT'])
                amount_comp_PROV_13AVO = abs(mapped_total['PROV_13AVO'])
                amount_comp_PROV_14AVO = abs(mapped_total['PROV_14AVO'])

                if line.employee_id.identification_id and line.employee_id.bank_account_id.sanitized_acc_number:
                    acc_number = line.employee_id.bank_account_id.sanitized_acc_number
                else:
                    acc_number = ''

                employees_data.append({
                    'name': line.employee_id.name.upper() or '',
                    'ident': line.employee_id.identification_id or line.employee_id.passport_id or '',
                    'member_account': acc_number,
                    'job_position': line.employee_id.job_title,
                    'period_start': self.date_from.strftime('%m/%d/%Y'),
                    'period_end': self.date_to.strftime('%m/%d/%Y'),
                    'first_date_of_employment': employee.contract_id.date_start.strftime(
                        '%m/%d/%Y') if employee.contract_id.date_start and employee.contract_id.date_start <= self.date_from else '',
                    'basic_salary': employee.contract_id.wage,
                    'worked_days': sum([line.number_of_days for p in payslips for line in p.worked_days_line_ids if not line.is_credit_time]),
                    'amount_basic': amount_basic,
                    'amount_variable': 0.00,
                    'amount_rounding': 0.00,
                    'amount_13avo_comp': 0.00,
                    'amount_car_atn': 0.00,
                    'amount_car_alw': 0.00,  # 'CAR.PRIV']
                    'amount_bonus': amount_bonus,
                    'amount_gross': amount_gross,
                    # 'amount_alter_bonus': amount_gross + amount_bonus,
                    'amount_prima': 0.00,
                    'amount_loan_car': 0.00,
                    'amount_alw_before_ihss': amount_alw,
                    'amount_ded_IHSS': amount_ded_IHSS,
                    'amount_ded_RAP': amount_ded_RAP,
                    'amount_tax': amount_tax,
                    'total_amount_ded_row': amount_alw + amount_ded_IHSS + amount_ded_RAP + amount_tax,
                    'amount_net': amount_net,
                    'amount_comp_patron': amount_comp_patron,
                    'amount_comp_patron_rap': amount_comp_patron_rap,
                    'amount_comp_patron_infop': amount_comp_patron_infop,
                    'amount_comp_PROV_13AVO': amount_comp_PROV_13AVO,
                    'amount_comp_PROV_14AVO': amount_comp_PROV_14AVO,
                    'last_date_of_employment': employee.contract_id.date_end.strftime(
                        '%m/%d/%Y') if employee.contract_id.date_end and employee.contract_id.date_end >= self.date_to else '',
                    # 'account_bank': acc_number,
                    # 'ref_bac': line.employee_id.bank_account_id.acc_holder_name or '',
                    # 'name_bac': line.employee_id.bank_account_id.partner_id.name or '',
                })
                total_amount_basic += amount_basic
                total_amount_gross += amount_gross
                total_amount_net += amount_net
                total_amount_bonus += amount_bonus

                total_amount_alw += amount_alw
                total_amount_ded_IHSS += amount_ded_IHSS
                total_amount_ded_RAP += amount_ded_RAP
                total_amount_tax += amount_tax
                total_amount_comp_patron += amount_comp_patron
                total_amount_comp_patron_rap += amount_comp_patron_rap
                total_amount_comp_patron_infop += amount_comp_patron_infop
                total_amount_comp_PROV_13AVO += amount_comp_PROV_13AVO
                total_amount_comp_PROV_14AVO += amount_comp_PROV_14AVO
                total_amount_alter_bonus += amount_gross + amount_bonus
                total_amount_ded_col += amount_alw + amount_ded_IHSS + amount_ded_RAP + amount_tax

            total_data = {
                'total_basic_salary': sum(all_employees.contract_id.mapped('wage')),
                'days': '',
                'total_amount_basic': total_amount_basic,
                'total_amount_variable': 0.00,
                'total_amount_rounding': 0.00,
                'total_amount_13avo_comp': 0.00,
                'total_amount_car_atn': 0.00,
                'total_amount_car_alw': 0.00,
                'total_amount_bonus': total_amount_bonus,
                # 'total_amount_alter_bonus': total_amount_alter_bonus,
                'total_amount_gross': total_amount_gross,
                'total_amount_prima': total_amount_prima,
                'total_amount_loan_car': 0.00,
                'total_amount_alw': total_amount_alw,
                'total_amount_ded_IHSS': total_amount_ded_IHSS,
                'total_amount_ded_RAP': total_amount_ded_RAP,
                'total_amount_tax': total_amount_tax,
                'total_amount_ded_col': total_amount_ded_col,
                'total_amount_net': total_amount_net,
                'total_amount_comp_patron': total_amount_comp_patron,
                'total_amount_comp_patron_rap': total_amount_comp_patron_rap,
                'total_amount_comp_patron_infop': total_amount_comp_patron_infop,
                'total_amount_comp_PROV_13AVO': total_amount_comp_PROV_13AVO,
                'total_amount_comp_PROV_14AVO': total_amount_comp_PROV_14AVO,
            }
            return {'employees_data': employees_data, 'total_data': total_data}
        else:
            return {'employees_data': [], 'total_data': []}

    def _fill_header_report(self, worksheet, options, name_struct_choice=''):
        def fill_header(sheet_val, header_title, subheaders=None):
            if not subheaders:
                sheet_val['sheet'].merge_range(5, sheet_val['index'], 6, sheet_val['index'], header_title,
                                               cell_format=options.get('style_highlight_left'))
                sheet_val['sheet'].set_column(sheet_val['index'], sheet_val['index'], int(len(header_title)) + 5)
                options.get('style_highlight_left').set_top(2)
                sheet_val['index'] += 1
            else:
                sheet_val['sheet'].merge_range(5, sheet_val['index'], 5, sheet_val['index'] + len(subheaders) - 1,
                                               header_title, cell_format=options.get('style_highlight'))
                options.get('style_highlight').set_top(2)
                sheet_val['sheet'].write_blank(5, sheet_val['index'] + len(subheaders) - 1, '')
                for sub_idx, subheader in enumerate(subheaders):
                    sheet_val['sheet'].set_column(sheet_val['index'], sheet_val['index'] + sub_idx,
                                                  int(len(subheader)) + 5)
                    sheet_val['sheet'].write(6, sheet_val['index'] + sub_idx, subheader, options.get('style_highlight'))
                sheet_val['index'] += len(subheaders)

        sheet_current_val = {'sheet': worksheet, 'index': 0}

        headers = [
            'No.',
            'Nombre del empleado',
            'Identidad',
            'Cuenta Bancaria',
            'Cargo',
            'Fecha de Ingreso',
            ('INGRESOS', (
                'Salario Básico', 'Días a pagar', 'Sueldo %s devengado' % name_struct_choice, 'Sueldo Variable',
                'Ajuste de salario', '13avo mes - complemento', 'Combustible', 'Car allowance', 'Premio',
                'Total Devengado')),
            ('DEDUCCIONES', (
                'Prima seguro médico por dependientes', 'Préstamo Vehículo', 'Subsidio IHSS', 'IHSS Laboral', 'RAP',
                'Impuesto Municipal', 'Total Deducc.')),
            'Neto a Recibir LEM',
            ('Contribuciones Patronales', ('Seguro Patronal', 'RAP', 'INFOP')),
            ('Provisiones del mes', ('Décimo tercer mes', 'Décimo cuarto mes')),
        ]
        struct_name = 'MENSUAL DEL MES'
        if name_struct_choice.upper() == 'QUINCENAL':
            if self.date_from.day < 15:
                struct_name = 'PRIMERA QUINCENA '
            else:
                struct_name = 'SEGUNDA QUINCENA '
        if name_struct_choice.upper() == 'SEMANAL':
            struct_name = 'SEMANA ' + self.date_from + '-' + self.date_to

        title_format = "{struct_name}" "{date_format}".format(
            struct_name= struct_name,
            date_format=self.date_from.strftime("%B %Y").upper()
        )
        company_name = self.company_id.name
        worksheet.merge_range('A1:G1', company_name,
                              cell_format=options.get('default_header_format'))
        worksheet.merge_range('A2:G2', 'NOMINA DE PAGO %s' % title_format,
                              cell_format=options.get('default_header_format'))

        for sheet_val in (sheet_current_val,):
            for header in headers:
                if isinstance(header, tuple):
                    fill_header(sheet_val, header[0], header[1])
                else:
                    fill_header(sheet_val, header)
        #
        # worksheet.merge_range('AM6:AO6', 'Para MACRO BAC', cell_format=options.get('style_highlight'))
        # worksheet.write_string('AM7:AM7', 'Referencia BAC', cell_format=options.get('style_normal').set_align('left'))
        # worksheet.set_column('AM7:AM7', 15)
        # worksheet.write_string('AN7:AN7', 'Cuenta BAC', cell_format=options.get('style_normal').set_align('left'))
        # worksheet.set_column('AN7:AN7', 20)
        # worksheet.write_string('AO7:AO7', 'Nombre', cell_format=options.get('style_normal').set_align('left'))
        # worksheet.set_column('AO7:AO7', 30)

    def _fill_row_report(self, worksheet, report, options):
        row = 7
        row_index = 1
        final_net = []
        if report and report['employees_data']:
            for employee_row in report['employees_data']:
                col = 1
                for employee_cel in employee_row:
                    worksheet.write_number(row, 0, row_index, cell_format=options.get('style_normal').set_align('right'))
                    if employee_cel not in ['period_start', 'period_end']:
                        if employee_cel == 'amount_net':
                            final_net.append(employee_row[employee_cel])
                        if employee_row[employee_cel]:
                            worksheet.write(row, col, employee_row[employee_cel], options.get('number_format'))
                        else:
                            worksheet.write_blank(row, col, '', options.get('number_format'))
                        col += 1
                row_index += 1
                row += 1

            worksheet.merge_range(row, 0, row, 5, 'TOTALES:', cell_format=options.get('style_highlight'))
            col = 6
            for key, value in report['total_data'].items():
                options.get('number_format_bold').set_border(1)
                worksheet.write(row, col, value, options.get('number_format_bold'))
                col += 1

            row = 7
            col += 2
            for net in final_net:
                worksheet.write_number(row, col, net, cell_format=options.get('number_format_bold'))
                row += 1

    def _fill_header_report_reducido(self, worksheet, options, name_struct_choice=''):
        def fill_header(sheet_val, header_title, subheaders=None):
            if not subheaders:
                sheet_val['sheet'].merge_range(5, sheet_val['index'], 6, sheet_val['index'], header_title,
                                               cell_format=options.get('style_highlight_left'))
                sheet_val['sheet'].set_column(sheet_val['index'], sheet_val['index'], int(len(header_title)) + 5)
                options.get('style_highlight_left').set_top(2)
                sheet_val['index'] += 1
            else:
                sheet_val['sheet'].merge_range(5, sheet_val['index'], 5, sheet_val['index'] + len(subheaders) - 1,
                                               header_title, cell_format=options.get('style_highlight'))
                options.get('style_highlight').set_top(2)
                sheet_val['sheet'].write_blank(5, sheet_val['index'] + len(subheaders) - 1, '')
                for sub_idx, subheader in enumerate(subheaders):
                    sheet_val['sheet'].set_column(sheet_val['index'], sheet_val['index'] + sub_idx,
                                                  int(len(subheader)) + 5)
                    sheet_val['sheet'].write(6, sheet_val['index'] + sub_idx, subheader, options.get('style_highlight'))
                sheet_val['index'] += len(subheaders)

        sheet_current_val = {'sheet': worksheet, 'index': 0}

        headers = [
            'No.',
            'Nombre del empleado',
            'Fecha de Ingreso',
            'Cargo',
            'Identidad',
            'Cuenta Bancaria',
            'Sueldo mensual',
            ('INGRESOS', (
                'Días', 'Devengado', 'Cantidad Horas Ext',
                'Horas Ext L.P.S', 'Otros Ingresos', 'Total Ingresos')),
            ('DEDUCCIONES', (
                'IHSS', 'RAP','ISR', 'Otros Egresos', 'Total Egresos')),
            'Neto a Pagar',
        ]
        struct_name = 'MENSUAL DEL MES'
        if name_struct_choice.upper() == 'QUINCENAL':
            if self.date_from.day < 15:
                struct_name = 'PRIMERA QUINCENA '
            else:
                struct_name = 'SEGUNDA QUINCENA '
        if name_struct_choice.upper() == 'SEMANAL':
            struct_name = 'SEMANA ' + self.date_from + '-' + self.date_to

        title_format = "{struct_name}" "{date_format}".format(
            struct_name= struct_name,
            date_format=self.date_from.strftime("%B %Y").upper()
        )
        company_name = self.company_id.name
        worksheet.merge_range('A1:G1', company_name,
                              cell_format=options.get('default_header_format'))
        worksheet.merge_range('A2:G2', 'NOMINA DE PAGO %s' % title_format,
                              cell_format=options.get('default_header_format'))

        for sheet_val in (sheet_current_val,):
            for header in headers:
                if isinstance(header, tuple):
                    fill_header(sheet_val, header[0], header[1])
                else:
                    fill_header(sheet_val, header)

    def _fill_row_report_reducido(self, worksheet, report, options):
        row = 7
        row_index = 1
        final_net = []
        if report and report['employees_data']:
            for employee_row in report['employees_data']:
                col = 1
                for employee_cel in employee_row:
                    worksheet.write_number(row, 0, row_index, cell_format=options.get('style_normal').set_align('right'))
                    if employee_cel not in ['period_start', 'period_end']:
                        if employee_cel == 'amount_net':
                            final_net.append(employee_row[employee_cel])
                        if employee_row[employee_cel]:
                            worksheet.write(row, col, employee_row[employee_cel], options.get('number_format'))
                        else:
                            worksheet.write_blank(row, col, '', options.get('number_format'))
                        col += 1
                row_index += 1
                row += 1

            worksheet.merge_range(row, 0, row, 5, 'TOTALES:', cell_format=options.get('style_highlight'))
            col = 6
            for key, value in report['total_data'].items():
                options.get('number_format_bold').set_border(1)
                worksheet.write(row, col, value, options.get('number_format_bold'))
                col += 1

            row = 7
            col += 2
            for net in final_net:
                worksheet.write_number(row, col, net, cell_format=options.get('number_format_bold'))
                row += 1

    def _generate_attachment(self):
        """ Function to create the PDF file.
            :param: values_dict All information about the partner
            :return: A PDF file
        """
        self.ensure_one()
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        if self.file_type == 'ampliado':
            statement_report_action = self.env.ref('l10n_hn_hr_payroll.action_report_monthly_summary')
            report_title = " Monthly Summary.pdf"
        elif self.file_type == 'reducido':
            statement_report_action = self.env.ref('l10n_hn_hr_payroll.action_report_monthly_summary')
            report_title = " Reducido Summary.pdf"
        else:
            statement_report_action = self.env.ref('l10n_hn_hr_payroll.action_report_bank_summary')
            report_title = " Bank Summary.pdf"
        for statement in self:
            statement_report = statement_report_action.sudo()
            content, _content_type = ir_actions_report_sudo._render_qweb_pdf(statement_report, res_ids=statement.ids, data={'company': statement.company_id})
            filename = _("%s %s " + report_title, statement.date_from.strftime("%d %B %Y"), statement.date_to.strftime("%d %B %Y"))
            statement.monthly_summary_pdf_filename = filename
            # statement.monthly_summary_pdf_file = base64.encodebytes(content)
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
        if self.file_type == 'ampliado':
            line_values = self._get_line_values()
        else:
            line_values = self._get_line_values_reducido()

        name_struct_choice = self.struct_id.name if self.struct_id else 'MENSUAL'
        title_format = "{struct_name}" "{date_format}".format(
            struct_name='PRIMERA QUINCENA ' if name_struct_choice.upper() == 'QUINCENAL' else 'PRIMERA SEMANA ' if name_struct_choice.upper() == 'SEMANAL' else 'DEL MES ' if name_struct_choice.upper() == 'MENSUAL' else name_struct_choice.upper(),
            date_format=self.date_from.strftime("%B %Y").upper()
        )
        line_values.update({'title_format': title_format})
        return line_values

    def action_print_payslip(self):
        self.ensure_one()
        self._generate_attachment()
        return {
            'type': 'ir.actions.act_url',
            'name': _("Monthly Summary PDF Download"),
            'url': f"/web/content/{self.pdf_attachment_id.id}?download=true",
            'close': True,
            "target": "new",
        }

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft',
            'xlsx_attachment_id': False,
            'pdf_attachment_id': False,
            'xlsx_filename': '',
            'monthly_summary_pdf_file': b'',
            'monthly_summary_pdf_filename': ''
        })

    def compute_sheet(self):
        self.action_reset_to_draft()
        self.action_generate_xls()
        self._generate_attachment()

    def _validate_form(self):
        self.ensure_one()
        if self.state != 'generated':
            self.write({
                'state': 'generated',
            })

    def action_generate_xls(self):
        if self.file_type == 'ampliado':
            line_values = self._get_line_values()
        else:
            line_values = self._get_line_values_reducido()
        self._validate_form()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Salary Report'))

        # Create a new Format
        default_header_format = workbook.add_format(
            {'font_size': 14, 'font_name': 'Arial', 'bold': True, 'text_wrap': True})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        number_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        number_format_bold = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        bold = workbook.add_format({'bold': True})
        style_highlight_left = workbook.add_format({'bold': True, 'align': 'left', 'border': 1, 'bg_color': '#FFFF99'})
        style_highlight = workbook.add_format({'bold': True, 'align': 'center', 'border': 1, 'bg_color': '#FFFF99'})
        style_normal = workbook.add_format({'align': 'center'})

        options = dict({'style_highlight': style_highlight, 'style_normal': style_normal,
                        'style_highlight_left': style_highlight_left, 'default_header_format': default_header_format,
                        'bold': bold, 'number_format': number_format,
                        'number_format_bold': number_format_bold, 'date_format': date_format})

        name_struct_choice = self.struct_id.name if self.struct_id else 'MENSUAL'

        if self.file_type == 'ampliado':
            self._fill_header_report(worksheet, options=options, name_struct_choice=name_struct_choice)
            self._fill_row_report(worksheet, line_values, options)
        else:
            self._fill_header_report_reducido(worksheet, options=options, name_struct_choice=name_struct_choice)
            self._fill_row_report_reducido(worksheet, line_values, options)

        workbook.close()

        if not self.xlsx_attachment_id:
            attachment = self.env["ir.attachment"].create({
                "name": self.xlsx_filename,
                "raw": output.getvalue(),
                "res_model": "l10n.hn.monthly.summary",
                "res_id": self.id,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            })
            self.xlsx_attachment_id = attachment
        else:
            self.xlsx_attachment_id.update({
                "name": self.xlsx_filename,
                "raw": output.getvalue(),
            })

class L10nMonthlySummaryLine(models.TransientModel):
    _name = 'l10n.hn.monthly.summary.line'
    _description = 'Monthly summary line'

    _sql_constraints = [
        ('unique_employee', 'unique(employee_id, sheet_id)', 'An employee can only have one line per sheet'),
    ]

    employee_id = fields.Many2one('hr.employee', required=True)
    sheet_id = fields.Many2one('l10n.hn.monthly.summary', required=True, ondelete='cascade')