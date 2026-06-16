from odoo import http, fields
from odoo.http import request
from _datetime import datetime
from odoo.addons.portal.controllers import portal


class SaleOrderPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_sales"):
            if "sale_order_checkout_count" in counters:
                count = request.env["sale.order"].sudo().search_count([])
                values["sale_order_checkout_count"] = count
        return values

     # show the sale data
    @http.route(["/sale/my", "/sale/my/page/<int:page>"], type="http", auth="user", website=True)
    def portal_sale_order_view(self, page=1, date_start=None, date_end=None, state=None, **kw):
        # Prepare domain based on filters
        domain = [("user_id", "=", request.env.user.id)]

        # Date filter
        if date_start:
            try:
                date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
                domain.append(("date_order", ">=", date_start))
            except ValueError:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
                domain.append(("date_order", "<=", date_end))
            except ValueError:
                pass

        # State filter
        if state:
            domain.append(("state", "=", state))

        # Get state labels for display
        state_labels = dict(
            request.env['sale.order'].fields_get(allfields=['state'])['state']['selection']
        )

        # Get sale orders with pagination
        sale_order_obj = request.env["sale.order"].sudo()
        total_count = sale_order_obj.search_count(domain)
        pager_data = portal.pager(
            url="/sale/my",
            total=total_count,
            page=page,
            step=self._items_per_page,
            scope=7,
            url_args=kw
        )

        orders = sale_order_obj.search(
            domain,
            limit=self._items_per_page,
            offset=pager_data['offset'],
            order='name desc'
        )
        total_amount = sum(o.amount_total for o in orders)

        # Prepare values for template
        values = {
            "orders": orders,
            'total_amount': total_amount,
            "pager": pager_data,
            "state_labels": state_labels,
            "date_start": date_start.strftime("%Y-%m-%d") if date_start else '',
            "date_end": date_end.strftime("%Y-%m-%d") if date_end else '',
            "state": state,
            "page_name": "sale_orders",
            "default_url": "/sale/my",
        }

        return request.render("pk_advance_employee_portal.ad_portal_sale_order_template", values)

    # show the form for new quotation request
    @http.route('/sale/my/create', type='http', auth='user', website=True)
    def create_sale_order_form(self, **kwargs):
        partners = request.env['res.partner'].sudo().search([])
        products = request.env['product.product'].sudo().search([])
        return request.render('pk_advance_employee_portal.ad_portal_create_sale_order_template', {
            'partners': partners,
            'products': products,
        })

     # create new quotation
    @http.route('/portal/sale_order/new', type='http', auth='user', website=True)
    def portal_create_sale_order_form(self, **kwargs):
        partners = request.env['res.partner'].sudo().search([])
        products = request.env['product.product'].sudo().search([], limit=100)
        return request.render('pk_advance_employee_portal.ad_portal_create_sale_order_template', {
            'partners': partners,
            'products': products,
        })

    @http.route('/portal/sale_order/create', type='http', auth='user', methods=['POST'], csrf=False)
    def create_sale_order(self, **post):
        partner_id = int(post.get('partner_id'))
        order_date = post.get('order_date')
        current_user = request.env.user

        # Create sale order
        order = request.env['sale.order'].sudo().create({
            'partner_id': partner_id,
            'date_order': order_date,
            'user_id': current_user.id,
        })

        # Process product lines
        product_lines = []
        for key, value in post.items():
            if key.startswith('product_id_') and value:
                index = key.split('_')[-1]
                product_lines.append((index, value))

        for index, product_id in product_lines:
            quantity_key = f'quantity_{index}'
            if quantity_key in post:
                product_id = int(product_id)
                quantity = float(post.get(quantity_key, 1))
                product = request.env['product.product'].sudo().browse(product_id)
                taxes = product.taxes_id.filtered(lambda t: t.company_id.id == order.company_id.id)

                request.env['sale.order.line'].sudo().create({
                    'order_id': order.id,
                    'product_id': product_id,
                    'product_uom_qty': quantity,
                    'price_unit': product.lst_price,
                    'tax_id': [(6, 0, taxes.ids)],
                })

        return request.redirect('/sale/my')

     # view the quotation/order
    @http.route('/view/my-quotation/<int:order_id>', type='http', auth='user', website=True)
    def view_user_quotation(self, order_id):
        order = request.env['sale.order'].sudo().browse(order_id)
        current_user = request.env.user

        # Show only if the current user is the salesperson of this quotation
        if not order.exists() or order.user_id.id != current_user.id:
            return request.redirect('/my/quotations')

        return request.render('pk_advance_employee_portal.ad_portal_quotation_detail_template', {
            'order': order,
        })



class SalespersonPortal(http.Controller):

    @http.route('/my/sales/dashboard', type='json', auth='user')
    def portal_sales_dashboard(self):
        user = request.env.user

        # Get sales orders for current user (assuming salesperson_id is linked to user)
        SaleOrder = request.env['sale.order'].sudo()

        draft_count = SaleOrder.search_count([
            ('state', '=', 'draft'),
            ('user_id', '=', user.id)
        ])
        sale_count = SaleOrder.search_count([
            ('state', '=', 'sale'),
            ('user_id', '=', user.id)
        ])
        cancelled_count = SaleOrder.search_count([
            ('state', '=', 'cancel'),
            ('user_id', '=', user.id)
        ])

        # Monthly Revenue (confirmed + done orders)
        today = fields.Date.today()
        first_day = today.replace(day=1)
        monthly_orders = SaleOrder.search([
            ('state', '=', 'sale'),
            ('user_id', '=', user.id),
            ('date_order', '>=', first_day),
            ('date_order', '<=', today)
        ])
        monthly_revenue = sum(monthly_orders.mapped('amount_total'))

        return {
            'draft_count': draft_count,
            'sale_count': sale_count,
            'cancelled_count': cancelled_count,
            'monthly_revenue': monthly_revenue,
        }

    @http.route(['/my/sales/dashboard/view'], type='http', auth='user', website=True)
    def portal_sales_dashboard_view(self, **kw):
        user = request.env.user
        SaleOrder = request.env['sale.order'].sudo()

        draft_count = SaleOrder.search_count([
            ('state', '=', 'draft'),
            ('user_id', '=', user.id)
        ])
        sale_count = SaleOrder.search_count([
            ('state', '=', 'sale'),
            ('user_id', '=', user.id)
        ])
        cancelled_count = SaleOrder.search_count([
            ('state', '=', 'cancel'),
            ('user_id', '=', user.id)
        ])
        # Monthly Revenue (confirmed + done orders)
        today = fields.Date.today()
        first_day = today.replace(day=1)
        monthly_orders = SaleOrder.search([
            ('state', '=', 'sale'),
            ('user_id', '=', user.id),
            ('date_order', '>=', first_day),
            ('date_order', '<=', today)
        ])
        monthly_revenue = sum(monthly_orders.mapped('amount_total'))

        values = {
            'draft_count': draft_count,
            'sale_count': sale_count,
            'cancelled_count': cancelled_count,
            'monthly_revenue': monthly_revenue,
        }
        return request.render('pk_advance_employee_portal.portal_sales_dashboard', values)


                    # edit the quotation
    @http.route('/customer/quotation/edit/<int:order_id>', type='http', auth='user', website=True,  csrf=False)
    def edit_customer_quotation(self, order_id, **kwargs):
        order = request.env['sale.order'].sudo().browse(order_id)
        # current_partner = request.env.user.partner_id
        current_user = request.env.user

        # Security check
        # if not order.exists() or order.user_id != request.env.user.id:
        #     return request.redirect('/customer/my')

        # Only allow edit if quotation is not confirmed
        if order.state not in ['draft']:
            return request.redirect(f'/view/my-customer/{order_id}')

        return request.render('pk_advance_employee_portal.portal_customer_edit_template', {
            'order': order,
        })
                # update the order

    @http.route('/portal/customer_order/update', type='http', auth='user', methods=['POST'], csrf=False)
    def update_customer_order(self, **post):
        order_id = int(post.get('order_id'))
        order = request.env['sale.order'].sudo().browse(order_id)

        # if not order.exists() or order.user_id != request.env.user.id:
        #     return request.redirect('/customer/my')

        # Dictionary to hold the state of existing lines
        existing_lines_to_update = {}

        # First pass: collect existing line data from the form
        for key, value in post.items():
            if key.startswith('product_'):
                line_id = int(key.split('_')[1])
                existing_lines_to_update[line_id] = {
                    'product_id': int(value),
                    'qty': float(post.get(f'qty_{line_id}', 1)),
                    'price': float(post.get(f'price_{line_id}', 0)),
                    'description': post.get(f'description_{line_id}', ''),
                }

        # Update and remove existing lines
        for line in order.order_line:
            line_data = existing_lines_to_update.get(line.id)
            if line_data:
                # Update existing line
                line.sudo().write({
                    'product_id': line_data['product_id'],
                    'product_uom_qty': line_data['qty'],
                    'name': line_data['description'],
                    'price_unit': line_data['price'],
                })
            else:
                # Line was removed from the form, so unlink it
                line.sudo().unlink()

        # Add new lines
        new_lines_data = []
        for key, value in post.items():
            if key.startswith('new_product_') and value:
                unique_id = key.split('_')[2]
                try:
                    product_id = int(value)
                    quantity = int(post.get(f'new_qty_{unique_id}', 1))
                    description = post.get(f'new_description_{unique_id}', '')
                except (ValueError, IndexError):
                    continue

                product = request.env['product.product'].sudo().browse(product_id)
                price_unit = product.lst_price

                # Check for an existing line to avoid duplicates on refresh
                if not any(nl['product_id'] == product_id for nl in new_lines_data):
                    new_lines_data.append({
                        'order_id': order.id,
                        'product_id': product_id,
                        'product_uom_qty': quantity,
                        'price_unit': price_unit,
                        'name': description,
                        'tax_id': [(6, 0, product.taxes_id.ids)],
                    })

        if new_lines_data:
            request.env['sale.order.line'].sudo().create(new_lines_data)

        return request.redirect(f'/my/orders/{order_id}')


