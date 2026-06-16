import base64

from odoo.addons.portal.controllers import portal
from odoo import http, fields
from odoo.http import request
from _datetime import datetime
from odoo.addons.portal.controllers.portal import pager, CustomerPortal


class MyExpensePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_expenses"):
            if "expense_checkout_count" in counters:
                count = request.env["hr.expense"].sudo().search_count([])
                values["expense_checkout_count"] = count
        return values

    @http.route(["/expense/my", "/expense/my/page/<int:page>"], type="http", auth="user", website=True)
    def portal_expense_my_view(self, page=1,date=None, date_end=None, state=None, **kw):
        expense_obj = request.env["hr.expense"].sudo()

        # Correct domain filter - using request.env.user instead of uid for clarity
        domain = [('employee_id.user_id', '=', request.env.user.id)]
        if date:
            try:
                date = datetime.strptime(date, "%Y-%m-%d").date()
                domain.append(("date", ">=", date))
            except ValueError:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
                domain.append(("date", "<=", date_end))
            except ValueError:
                pass

            # State filter
        if state:
            domain.append(("state", "=", state))

            # Get state labels for display
        state_labels = dict(
            request.env['hr.expense'].fields_get(allfields=['state'])['state']['selection']
        )

        # Get total count
        checkout_count = expense_obj.search_count(domain)

        # Prepare pager data
        pager_data = portal.pager(
            url="/expense/my",
            total=checkout_count,
            page=page,
            step=self._items_per_page,
        )

        # Get expenses with pagination
        expenses = expense_obj.search(
            domain,
            limit=self._items_per_page,
            offset=pager_data["offset"],
            order='date desc'  # Add sorting
        )

        # Prepare values
        values = {
            'expenses': expenses,
            'page_name': 'expense_my',
            'default_url': '/expense/my',
            'state_labels': state_labels,
            "date": date.strftime("%Y-%m-%d") if date else '',
            "date_end": date_end.strftime("%Y-%m-%d") if date_end else '',
            "state": state,
            'pager': pager_data,
            'user': request.env.user
        }

        # Update with portal layout values
        values.update(self._prepare_portal_layout_values())

        return request.render("pk_advance_employee_portal.ad_portal_my_expenses", values)


    # request new expense
    @http.route('/expense/new', type='http', auth="user", website=True)
    def new_expense_form(self, **kw):
        # Get products that can be expensed
        products = request.env['product.product'].sudo().search([('can_be_expensed', '=', True)])
        return request.render("pk_advance_employee_portal.ad_expense_submission_form", {
            'products': products,
            'employee': request.env.user.employee_id
        })

    @http.route('/expense/submit', type='http', auth="user", website=True, methods=['POST'], csrf=False)
    def submit_expense(self, **post):
        # Get and sanitize inputs
        name = post.get('name') or 'Expense'
        product_id_str = post.get('product_id')
        total_amount = float(request.httprequest.form.get('total_amount') or 0.0)
        employee_id = request.env.user.employee_id.id
        description = post.get('description', '')
        payment_mode = post.get('payment_mode')  # 'own_account' or 'company_account'

        # Validate product_id
        if not product_id_str or not product_id_str.isdigit():
            return request.redirect('/expense/new')

        product_id = int(product_id_str)

        # Handle file upload
        receipt_file = request.httprequest.files.get('receipt')
        attachment_data = False
        attachment_name = ''
        mimetype = ''
        if receipt_file:
            attachment_data = base64.b64encode(receipt_file.read())
            attachment_name = receipt_file.filename
            mimetype = receipt_file.mimetype

        # Create expense record
        expense_vals = {
            'name': name,
            'product_id': product_id,
            'total_amount': total_amount,
            'employee_id': employee_id,
            'description': description,
            'payment_mode': payment_mode,  # Custom field you must define
        }

        expense = request.env['hr.expense'].sudo().create(expense_vals)

        # Attach uploaded receipt if present
        if attachment_data:
            request.env['ir.attachment'].sudo().create({
                'name': attachment_name,
                'type': 'binary',
                'datas': attachment_data,
                'res_model': 'hr.expense',
                'res_id': expense.id,
                'mimetype': mimetype,
            })

        return request.redirect('/expense/my')