from odoo import http
from odoo.http import route, request
from odoo.addons.portal.controllers import portal


class WeeklyCustomerPortal(portal.CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_schedule"):
            if "weekly_checkout_count" in counters:
                count = request.env["planning.slot"].sudo().search_count([])
                values["weekly_checkout_count"] = count
        return values

    @route(["/weekly/schedule", "/weekly/schedule/page/<int:page>"],type="http", auth="user", website=True, )
    def portal_weekly_form_view(self, page=1, **kw):
        checkout = request.env["planning.slot"].sudo()
        current_user = request.env.user
        employee = current_user.employee_id

        domain = []
        if employee:
            domain = [('employee_id', '=', employee.id), ('state', '=', 'published')]
        else:
            # fallback for users with no employee linked
            domain = [('employee_id.user_id', '=', current_user.id), ('state', '=', 'published')]

        # Prepare pager data
        checkout_count = checkout.search_count(domain)
        pager_data = portal.pager(
            url="/weekly/schedule",
            total=checkout_count,
            page=page,
            step=self._items_per_page,
        )
        # Recordset according to pager and domain filter
        checkouts = checkout.search(domain, limit=self._items_per_page, offset=pager_data["offset"], )
         # Prepare template values and render
        values = self._prepare_portal_layout_values()

        values.update({"checkouts": checkouts,
                       "page_name": "weekly_schedule",
                       "default_url": "/weekly/schedule",
                       "pager": pager_data,
                       "user": request.env.user})
        return request.render("pk_advance_employee_portal.ad_weekly_schedule_form_view_temp_id", values)

    @http.route(["/weekly/schedule/form/<model('hr.leave'):leave_id>"],type="http", auth="user", website=True)
    def portal_weekly_list_view(self, leave_id, **kw):
        vals = {'doc':leave_id, "user": request.env.user}
        return request.render("pk_advance_employee_portal.ad_weekly_schedule_form_view_temp_id", vals)


    # new request form rout
    @http.route(['/weekly-schedule/new'], type='http', auth="user", website=True)
    def portal_weekly_schedule_form(self, **kw):
        return request.render("pk_advance_employee_portal.ad_weekly_schedule__template", {})

    # submit the form rout
    @http.route(['/weekly-schedule/request'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_weekly_schedule_submit(self, **post):
        resource_id = post.get('resource_id')
        start_datetime = post.get('start_datetime')
        end_datetime = post.get('end_datetime')
        role_id = post.get('role_id')
        company_id = post.get('company_id')

        employee = request.env.user.employee_id

        if employee:
            request.env['planning.slot'].sudo().create({
                'employee_id': employee.id,
                'resource_id': int(resource_id),
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'role_id': int(role_id),
                'company_id': int(company_id),
            })

        return request.redirect('/weekly/schedule')