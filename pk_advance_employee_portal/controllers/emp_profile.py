import datetime

from odoo.addons.portal.controllers import portal
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmployeeProfilePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_emp_profile"):
            if "empl_profile" in counters:
                count = request.env["hr.employee"].sudo().search_count([])
                values["empl_profile"] = count
        return values

    @http.route(["/my/profile", "/my/profile/page/<int:page>"], type="http", auth="user", website=True)
    def portal_my_profile_form_view(self, page=1, **kw):
        Employee = request.env["hr.employee"].sudo()
        user = request.env.user

        # Find the employee record for the logged-in user
        employee = Employee.search([("user_id", "=", user.id)], limit=1)

        if not employee:
            return request.render("pk_advance_employee_portal.no_employee_found_template", {})

        # Render template with employee data
        return request.render(
            "pk_advance_employee_portal.ad_my_profile_tem_id",
            {"employee": employee},
        )


    @http.route(['/edit/profile'], type='http', auth='user', website=True, csrf=False, methods=['POST', 'GET'])
    def portal_edit_profile_form_view(self, **post):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.uid)], limit=1)
        if not employee:
            return request.not_found()

        # If it's a POST request, save the data
        if request.httprequest.method == 'POST':

            vals = {
                "private_email": post.get("private_email"),
                "private_phone": post.get("private_phone"),
                "bank_account_id": int(post.get("bank_account_id")) if post.get("bank_account_id") else False,
                "distance_home_work": post.get("distance_home_work"),
                "private_car_plate": post.get("private_car_plate"),
                "country_id": int(post.get("country_id")) if post.get("country_id") else False,
                "identification_id": post.get("identification_id"),
                "ssnid": post.get("ssnid"),
                "passport_id": post.get("passport_id"),
                "gender": post.get("gender"),
                "birthday": post.get("birthday"),
                "place_of_birth": post.get("place_of_birth"),
                "country_of_birth": int(post.get("country_of_birth")) if post.get("country_of_birth") else False,
                "marital": post.get("marital") or "single",
                "children": post.get("children"),
                "emergency_contact": post.get("emergency_contact"),
                "emergency_phone": post.get("emergency_phone"),
                "certificate": post.get("certificate"),
                "study_field": post.get("study_field"),
                "study_school": post.get("study_school"),
                "visa_no": post.get("visa_no"),
                "permit_no": post.get("permit_no"),
                "visa_expire": post.get("visa_expire"),
                "work_permit_expiration_date": post.get("work_permit_expiration_date"),
            }

            employee.sudo().write(vals)
            return request.redirect("/my/profile")

        # If it's a GET request, render the form with current employee values
        return request.render("pk_advance_employee_portal.ad_my_profile_edit_template", {
            "employee": employee
        })


        # ==== Experience Page ====
    @http.route(['/my/experience'], type='http', auth="user", website=True)
    def my_experience(self, **kw):
        employee = request.env.user.employee_id
        return request.render("pk_advance_employee_portal.my_experience_template", {
            'employee': employee,
            'experience_ids': employee.resume_line_ids,
        })

    @http.route(['/edit/experience'], type='http', auth="user", website=True, methods=['GET', 'POST'], csrf=False)
    def edit_experience(self, **post):
        employee = request.env.user.employee_id
        if request.httprequest.method == 'POST':
            # create new experience record
            request.env['hr.resume.line'].sudo().create({
                'employee_id': employee.id,
                'name': post.get('name'),
                'line_type_id': post.get('line_type_id'),
                'date_start': post.get('date_start'),
                'date_end': post.get('date_end'),
            })
            return request.redirect('/my/experience')
        return request.render("pk_advance_employee_portal.edit_experience_template", {
            'employee': employee,
        })

    # ==== Skills Page ====
    @http.route(['/my/skills'], type='http', auth="user", website=True)
    def my_skills(self, **kw):
        employee = request.env.user.employee_id
        skills = request.env['hr.employee.skill'].sudo().search([
            ('employee_id', '=', employee.id)
        ])
        return request.render("pk_advance_employee_portal.my_skills_template", {
            'employee': employee,
            'skills': skills
        })

    @http.route(['/edit/skills'], type='http', auth="user", website=True, methods=['GET', 'POST'], csrf=False)
    def add_skill(self, **post):
        employee = request.env.user.employee_id

        if request.httprequest.method == 'POST':
            request.env['hr.employee.skill'].sudo().create({
                'employee_id': employee.id,
                'skill_id': int(post.get('skill_id')),
                'skill_level_id': int(post.get('skill_level_id')),
            })
            return request.redirect('/my/skills')

        skill_types = request.env['hr.skill.type'].sudo().search([])
        skills = request.env['hr.skill'].sudo().search([])
        skill_levels = request.env['hr.skill.level'].sudo().search([])

        return request.render("pk_advance_employee_portal.edit_skills_template", {
            'skill_types': skill_types,
            'skills': skills,
            'skill_levels': skill_levels,
        })
