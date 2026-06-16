from odoo.addons.portal.controllers import portal
from odoo import http, fields
from odoo.fields import Date
from odoo.http import route, request
from odoo.addons.portal.controllers.portal import CustomerPortal


class InheritCustomerPortal(CustomerPortal):

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        # Simply render the template without any additional processing
        return request.render('pk_advance_employee_portal.pk_advance_portal_my_home')

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_leaves"):
            if "book_checkout_count" in counters:
                count = request.env["hr.leave"].sudo().search_count([])
                values["book_checkout_count"] = count
        return values

    @route(["/employee/leaves", "/employee/leaves/page/<int:page>"], type="http", auth="user", website=True)
    def portal_employee_leave_form_view(self, page=1, **kw):
        # Elevate privileges for hr.leave model operations
        checkout = request.env["hr.leave"].sudo()
        user = request.env.user


        domain = [('employee_id.user_id', '=', request.env.uid)]

        # Prepare pager data
        checkout_count = checkout.search_count(domain)
        pager_data = portal.pager(
            url="/employee/leaves",
            total=checkout_count,
            page=page,
            step=self._items_per_page,
        )

        # Recordset according to pager and domain filter
        checkouts = checkout.search(domain, limit=self._items_per_page, offset=pager_data["offset"])

        # Prepare template values and render
        values = self._prepare_portal_layout_values()

        # to sum the total leave of employee
        # to sum the total leave of employee
        days_off = checkout.search([('employee_id.user_id', '=', request.env.uid), ('state', '=', 'validate')])
        total_leave_days = sum(days_off.mapped('number_of_days'))

        # Calculate taken leaves (past dates)
        taken_leaves = days_off.filtered(lambda leave: leave.date_from < fields.Datetime.now())
        taken_leave_days = sum(taken_leaves.mapped('number_of_days'))

        # Calculate scheduled leaves (future dates)
        scheduled_leaves = days_off.filtered(lambda leave: leave.date_from >= fields.Datetime.now())
        scheduled_leave_days = sum(scheduled_leaves.mapped('number_of_days'))

        # Get unique leave types
        leave_types = days_off.mapped('holiday_status_id')

        # Initialize dictionaries to store leave days by type
        taken_leave_days_by_type = {}
        scheduled_leave_days_by_type = {}

        # Iterate over leave types
        for leave_type in leave_types:
            taken_leaves_of_type = taken_leaves.filtered(lambda leave: leave.holiday_status_id == leave_type)
            taken_leave_days_by_type[leave_type.name] = sum(taken_leaves_of_type.mapped('number_of_days'))

            scheduled_leaves_of_type = scheduled_leaves.filtered(lambda leave: leave.holiday_status_id == leave_type)
            scheduled_leave_days_by_type[leave_type.name] = sum(
                scheduled_leaves_of_type.mapped('number_of_days'))

        values.update({
            "checkouts": checkouts,
            "page_name": "employee_leave",
            "taken_leaves": taken_leaves,
            "scheduled_leaves": scheduled_leaves,
            "days_off": total_leave_days,
            "taken_leave_days": taken_leave_days,
            "scheduled_leave_days": scheduled_leave_days,
            "taken_leave_days_by_type": taken_leave_days_by_type,
            "scheduled_leave_days_by_type": scheduled_leave_days_by_type,
            "default_url": "/employee/leaves",
            "pager": pager_data,
            "user": user,
        })

        return request.render("pk_advance_employee_portal.ad_employee_leave_form_view_temp_id", values)


    @http.route(["/employee/leave/<model('hr.leave'):leave_id>"], type="http", auth="user", website=True)
    def portal_employee_leave_list_view(self, leave_id, **kw):

        vals = {'doc': leave_id,
                "user": request.env.user,
                }
        return request.render("pk_advance_employee_portal.ad_employee_leave_list_view_temp_id", vals)


    # create new request template
    @http.route(['/my/leaves/new'], type='http', auth="user", website=True)
    def portal_leave_create_form(self, **kw):
        return request.render("pk_advance_employee_portal.ad_portal_leave_create_template", {})

    # create new leave request from portal side controller

    @http.route(['/my/leaves/create'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_leave_create_submit(self, **post):
        leave_type_id = int(post.get('leave_type'))
        date_from = post.get('request_date_from')
        date_to = post.get('request_date_to')
        reason = post.get('reason')
        employee = request.env.user.employee_id

        if not (leave_type_id and employee):
            return request.render('http_routing.error_message', {
                'error_message': 'Missing leave type or employee information.'
            })

        # Convert to date objects
        date_from_obj = Date.from_string(date_from)
        date_to_obj = Date.from_string(date_to)
        requested_days = (date_to_obj - date_from_obj).days + 1

        # Check if there is a valid allocation
        allocation = request.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type_id),
            ('state', '=', 'validate'),
            ('duration_display', '>=', requested_days)
        ], limit=1)

        if not allocation:
            return request.render('http_routing.error_message', {
                'error_message': 'There is no valid leave allocation for the selected type.'
            })

        # Create the leave request
        request.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'holiday_status_id': leave_type_id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'date_from': date_from,
            'date_to': date_to,
            'name': reason or "Leave Request from Portal",
        })

        return request.redirect('/employee/leaves')