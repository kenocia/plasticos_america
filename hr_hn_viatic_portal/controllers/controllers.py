# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PortalViaticCustom(http.Controller):
    
    @http.route(['/hr_expense/get_employees'], type='json', auth="user", website=True)
    def get_employees(self, **kwargs):
        employees = request.env['hr.employee'].sudo().search([('company_id', '=', request.env.company.id)])
        return [{"id": emp.id, "name": emp.name} for emp in employees]
    
    @http.route(['/hr_expense/get_user'], type='json', auth="user", website=True)
    def get_user(self, **kwargs):
        user_employee_id = request.env.user.employee_id.id if request.env.user.employee_id else None
        return user_employee_id 
    
    @http.route(['/hr_expense/get_products'], type='json', auth="user", website=True)
    def get_products(self, **kwargs):
        product_ids = request.env['product.product'].sudo().search(
            [('can_be_expensed', '=', True), '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)]
        )
        return [{"id": prod.id, "name": prod.name} for prod in product_ids]
    
    @http.route(['/create_viatic_hr_expense/new'], type='http', auth="user", website=True)
    def create_viatic_hr_expense(self, **kwargs):
        company_id = request.env.company.id
        currency_id = request.env.company.currency_id

        currency_ids = request.env['res.currency'].sudo().search([('active', '=', True)])

        tax_ids = request.env['account.tax'].sudo().search(
            [('company_id', '=', company_id), ('type_tax_use', '=', 'purchase')]
        )

        employee_ids = request.env['hr.employee'].sudo().search([('company_id', '=', company_id)])

        user_employee_id = request.env.user.employee_id.id if request.env.user.employee_id else None

        payment_mode = request.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.expense'), ('name', '=', 'payment_mode')]
        )
        payment_mode_ids = request.env['ir.model.fields.selection'].sudo().search([('field_id', '=', payment_mode.id)])

        return request.render('hr_hn_viatic_portal.viatic_form_template', {
            'tax_ids': tax_ids,
            'employee_ids': employee_ids,
            'payment_mode_ids': payment_mode_ids,
            'currency_ids': currency_ids,
            'default_currency_id': currency_id,
            'user_employee_id': user_employee_id,  
        })
    
    

    @http.route(['/my/viatic/list'], type='http', auth="user", website=True)
    def portal_page(self, page=0, **kwargs):
        items_per_page = 80
        page = int(page)

        # Obtener el usuario actual
        user_id = request.env.user

        # Filtrar registros del modelo por usuario
        Model = request.env['hr.hn.viatic'].sudo()
        total_items = Model.search_count([('create_uid', '=', user_id.id)])
        total_pages = (total_items - 1) // items_per_page + 1
        items = Model.search([('create_uid', '=', user_id.id)], offset=page * items_per_page, limit=items_per_page)

        # Renderizar la vista con los datos filtrados
        return request.render('hr_hn_viatic_portal.template_list_of_viatic', {
            'items': items,
            'page': page,
            'total_pages': total_pages,
        })



    @http.route('/safe_hr_viatic_expense', methods=["POST"], type="json", auth="user", website=True)
    def create_viatic_form(self, viatic):
        # Convertir employees_ids de cadena a lista
        employees_ids_raw = viatic.get('employees_ids', '')
        employees_ids = list(map(int, employees_ids_raw.split(','))) if employees_ids_raw else []

        viatic_res = request.env['hr.hn.viatic'].sudo().create({
            'name': viatic.get('name'),
            'place': viatic.get('place'),
            'date': viatic.get('date'),
            'travel_to': viatic.get('travel_to'),
            'reason_description': viatic.get('reason_description'),
            'date_ini': viatic.get('date_ini'),
            'date_end': viatic.get('date_end'),
            'employee_id': int(viatic.get('employee_id')),
            'employees_ids': [(6, 0, employees_ids)],
        })
        expense_line_records = []
        for expense_line_vals in viatic.get('expense_line_ids'):

            aux = expense_line_vals
            aux['product_id'] = int(aux['product_id'].get('id', 0))
            expense_line = request.env['hr.expense'].sudo().create(aux)
            expense_line_records.append((4, expense_line.id))

        viatic_res.write({
            'expense_line_ids': expense_line_records
        })
