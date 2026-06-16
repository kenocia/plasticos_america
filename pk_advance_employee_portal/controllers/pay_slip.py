from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.portal.controllers.portal import pager, CustomerPortal


class EmployeePayrollPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_employee_payroll_portal.ad_group_payroll"):
            if "my_payroll" in counters:
                count = request.env["hr.payslip"].sudo().search_count([])
                values["my_payroll"] = count
        return values

    @http.route(['/my/payslips'], type='http', auth="user", website=True)
    def my_payslips(self, **kwargs):
        employee = request.env.user.employee_id
        payslips = request.env['hr.payslip'].sudo().search([
            ('employee_id', '=', employee.id)
        ], order='date_from desc')
        return request.render("pk_advance_employee_portal.my_payslips_template", {
            'payslips': payslips
        })

    @http.route(['/my/payslip/<int:payslip_id>/pdf'], type='http', auth="user")
    def portal_print_payslip(self, payslip_id, **kwargs):
        # 1. Security check without sudo
        payslip = request.env['hr.payslip'].browse(payslip_id)
        if not payslip or not payslip.exists():
            return request.not_found()
        if payslip.employee_id.user_id != request.env.user:
            return request.not_found()

        # 2. Get the built-in payroll report action
        report_action = request.env.ref('hr_payroll.action_report_payslip').sudo()

        # 3. Generate the PDF for this payslip
        pdf_content, _ = report_action._render_qweb_pdf('hr_payroll.action_report_payslip',res_ids=[payslip.id])

        # 4. Return as downloadable PDF
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', content_disposition(f'Payslip-{payslip.employee_id.name}.pdf')),
        ]
        return request.make_response(pdf_content, headers=pdfhttpheaders)