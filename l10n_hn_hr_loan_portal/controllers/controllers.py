# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from odoo.addons.portal.controllers.portal import CustomerPortal as CustomerPortal


class PortalQuitCustom(http.Controller):
    @http.route(['/create_loan/new'], type='http', auth="user", website=True)
    def create_loan_request(self, **kwargs):
        company_id = request.env.company.id
        employee_id = request.env.user.employee_id
        loan_date = datetime.now().date()
        values = ({
            'employee_id': employee_id,
            'date': loan_date,
            'loan_amount': 0,
            'installment': 0,
            'payment_date': loan_date,
        })
        return request.render('l10n_hn_hr_loan_portal.loan_form_template', values)

    @http.route(["/my/loan/list"], type='http', auth="user", website=True)
    def portal_page(self, page=0, **kwargs):
        # Definir la cantidad de elementos por página
        items_per_page = 80
        page = int(page)

        # Obtener el modelo que quieres mostrar
        Model = request.env['hr.loan'].sudo()

        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        # employee_id = request.env['hr.employee'].sudo().search([('portal_user_id', '=', user_id), ('is_employee_expense_portal', '=', True)])
        # Contar el total de elementos
        total_items = Model.search_count([('employee_id', '=', employee_id.id)])

        # Calcular el total de páginas
        total_pages = (total_items - 1) // items_per_page + 1

        # Obtener los elementos para la página actual
        items = Model.search([('employee_id', '=', employee_id.id)], offset=page * items_per_page, limit=items_per_page)

        return request.render('l10n_hn_hr_loan_portal.template_list_of_loan', {
            'items': items,
            'page': page,
            'total_pages': total_pages,
        })

    @http.route('/safe_hr_loan', methods=["POST"], type="json", auth="user", website=True)
    def create_loan_form(self, loan_request):
            loan_request_res = request.env['hr.loan'].sudo().create({
                'employee_id': loan_request.get('employee_id'),
                'date': loan_request.get('date'),
                'loan_amount': loan_request.get('loan_amount'),
                'installment': loan_request.get('installment'),
                'payment_date': loan_request.get('payment_date'),
            })

    @http.route('/loan/answer_form', type='http', auth='user', website=True)
    def render_answer_form(self):
        return http.request.render('l10n_hn_hr_loan_portal.answer_form')

    @http.route(['/detail/loan'], type='http', auth="user", website=True)
    def loan_detail(self, loan_id=0, **kwargs):
        loan_id = request.env['hr.loan'].sudo().browse(int(loan_id))

        return request.render('l10n_hn_hr_loan_portal.model_record_loan', {
            'record': loan_id,
        })

class L10nHnHrCustomerPortal(CustomerPortal):

    def home(self, **kw):
        res = super(L10nHnHrCustomerPortal, self).home(**kw)

        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        qcontext = res.qcontext.copy()
        if employee_id:
            qcontext['is_empl'] = True
        else:
            qcontext['is_empl'] = False
        res.qcontext = qcontext
        return res
