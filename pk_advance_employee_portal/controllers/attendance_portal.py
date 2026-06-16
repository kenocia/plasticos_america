# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers import portal

from datetime import datetime, timedelta

class AttendancePortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_attendance_access"):
            if "attendance_checkin_out" in counters:
                count = request.env["sale.order"].sudo().search_count([])
                values["attendance_checkin_out"] = count
        return values

    _items_per_page = 10  # number of records per page

    @http.route(['/attendance/my', '/attendance/my/page/<int:page>'], type='http', auth='user', website=True)
    def portal_attendance_list(self, page=1, date_start=None, date_end=None, **kw):
        # get employee linked to current user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return request.redirect('/my')  # or show a message page

        domain = [('employee_id', '=', employee.id)]

        # filter by date
        if date_start:
            try:
                date_start = datetime.strptime(date_start, "%Y-%m-%d")
                domain.append(('check_in', '>=', date_start))
            except Exception:
                pass

        if date_end:
            try:
                date_end = datetime.strptime(date_end, "%Y-%m-%d")
                # Include full day by adding 1 day and subtracting 1 second
                date_end = date_end + timedelta(days=1) - timedelta(seconds=1)
                domain.append(('check_in', '<=', date_end))
            except Exception:
                pass

        attendance_model = request.env['hr.attendance'].sudo()
        total_count = attendance_model.search_count(domain)

        pager = portal.pager(
            url="/attendance/my",
            total=total_count,
            page=page,
            step=self._items_per_page,
            scope=7,
            url_args=kw
        )

        records = attendance_model.search(
            domain,
            limit=self._items_per_page,
            offset=pager['offset'],
            order='check_in desc'
        )
        # Find active attendance (not yet checked out)
        active_attendance = attendance_model.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)

        values = {
            'attendances': records,
            'pager': pager,
            'date_start': date_start.strftime("%Y-%m-%d") if date_start else '',
            'date_end': date_end.strftime("%Y-%m-%d") if date_end else '',
            'page_name': 'attendance_my',
            'employee': employee,
            'active_attendance': active_attendance,
        }

        return request.render("pk_advance_employee_portal.portal_attendance_view", values)


    # --- Punch In ---
    @http.route(['/attendance/check_in'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_check_in(self, **kw):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if employee:
            now = fields.Datetime.now()
            today_start = fields.Date.to_date(fields.Date.context_today(employee))
            today_end = today_start + timedelta(days=1) - timedelta(seconds=1)

            existing_attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today_start),
                ('check_in', '<=', today_end),
            ], limit=1)

            if existing_attendance:
                request.session['warning'] = "You have already checked in today."
            else:
                user_agent = request.httprequest.headers.get('User-Agent', 'Unknown')
                ip_address = request.httprequest.remote_addr
                gps_location = kw.get("gps_location")

                lat, lng = (0.0, 0.0)
                if gps_location and "," in gps_location:
                    lat, lng = gps_location.split(",")

                request.env['hr.attendance'].sudo().create({
                    'employee_id': employee.id,
                    'check_in': now,
                    'in_browser': user_agent,
                    'in_ip_address': ip_address,
                    'in_latitude': lat,
                })
        return request.redirect('/attendance/my')

    @http.route(['/attendance/check_out'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def attendance_check_out(self, **kw):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if employee:
            today_start = fields.Date.to_date(fields.Date.context_today(employee))
            today_end = today_start + timedelta(days=1) - timedelta(seconds=1)

            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today_start),
                ('check_in', '<=', today_end),
                ('check_out', '=', False),
            ], limit=1)

            if attendance:
                user_agent = request.httprequest.headers.get('User-Agent', 'Unknown')
                ip_address = request.httprequest.remote_addr
                gps_location = kw.get("gps_location")

                lat, lng = (0.0, 0.0)
                if gps_location and "," in gps_location:
                    lat, lng = gps_location.split(",")

                attendance.sudo().write({
                    'check_out': fields.Datetime.now(),
                    'out_browser': user_agent,
                    'in_ip_address': ip_address,
                    'out_latitude': lat,
                })
        return request.redirect('/attendance/my')