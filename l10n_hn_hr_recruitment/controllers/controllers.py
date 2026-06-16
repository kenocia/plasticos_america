# -*- coding: utf-8 -*-
import json
import re
import unicodedata
import datetime
from odoo import http, _
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment as WebsiteHrRecruitment
from odoo.addons.website.controllers.form import WebsiteForm as WebsiteForm
from odoo.addons.portal.controllers.portal import CustomerPortal as CustomerPortal
from datetime import datetime, timedelta

class l10nWebsiteHrRecruitment(WebsiteHrRecruitment):

    def job(self, job, **kwargs):
        return request.render("website_hr_recruitment.detail", {
            'job': job,
            'main_object': job,
        })

    @http.route('''/jobs/detail/<model("hr.job"):job>''', type='http', auth="public", website=True, sitemap=True)
    def jobs_detail(self, job, **kwargs):
        redirect_url = f"/jobs/{self.slugify(job)}"
        return request.redirect(redirect_url, code=301)
        

    @http.route('''/jobs/apply/new''', type='http', auth="public", website=True, sitemap=True)
    def jobs_apply(self, job, **kwargs):
        error = {}
        default = {}
        if 'website_hr_recruitment_error' in request.session:
            error = request.session.pop('website_hr_recruitment_error')
            default = request.session.pop('website_hr_recruitment_default')
        return request.render("website_hr_recruitment.apply", {
            'job': job,
            'error': error,
            'default': default,
        })
        
    def jobs(self, country_id=None, department_id=None, office_id=None, contract_type_id=None,
             is_remote=False, is_other_department=False, is_untyped=None, page=1, search=None, **kwargs):
        res = super(l10nWebsiteHrRecruitment, self).jobs(country_id, department_id, office_id, contract_type_id,
             is_remote, is_other_department, is_untyped, page, search, **kwargs)
        qcontext = res.qcontext.copy()

        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        jobs = request.env['hr.job'].sudo().search(['|', ('internal_published', '=', True), ('is_published', '=', True)])
        qcontext['jobs'] = jobs
        if employee_id:
            qcontext['is_empl'] = True
            qcontext['show_internal'] = True
            if employee_id.id in user_id.company_id.selection_portal.ids:
                qcontext['empl_sel'] = True
            else:
                qcontext['empl_sel'] = False
        else:
            qcontext['show_internal'] = False
            qcontext['is_empl'] = False
            qcontext['empl_sel'] = False

        # Actualizar el contexto en el resultado
        res.qcontext = qcontext
        return res

    def jobs_apply(self, job, **kwargs):
        res = super(l10nWebsiteHrRecruitment, self).jobs_apply(job, **kwargs)
        user_id = request.env.user
        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        
        context = res.qcontext.copy()
        context['document_type_ids'] = job.sudo().document_type_ids
        
        if employee_id:
            # Nombre completo estándar de hr.employee (sin hr_hn_employee_lastnames)
            context['firstname'] = employee_id.name or ''
            context['firstname2'] = False
            context['lastname'] = False
            context['lastname2'] = False

        res.qcontext = context

        return res

    @http.route('''/candidatos/solicitudes/''', type='http', auth="public", website=True, sitemap=True)
    def show_list_applicant(self, job, **kwargs):
        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        if employee_id and employee_id.id in user_id.company_id.selection_portal.ids:
            applicant_ids = request.env['hr.applicant'].sudo().search([('company_id', '=', user_id.company_id.id),
                                                                       ('job_id', '=', job),
                                                                       ('department_id', '=',
                                                                        employee_id.department_id.id)])
            if applicant_ids:
                return request.render("l10n_hn_hr_recruitment.jobs_candidates_applicant_list", {
                    'applicant_ids': applicant_ids,
                    'show_list': True,
                    'job_id': job
                })
        return request.render("l10n_hn_hr_recruitment.jobs_candidates_applicant_list", {
            'applicant_ids': [],
            'show_list': False,
            'job_id': job
        })

    @http.route("/approve_candidates", methods=["POST"], type="json", auth="user")
    def create_approve_candidates(self, app_list, job_id):
        applicant = request.env['hr.applicant'].sudo()
        applicant_ids_int = list(map(int, app_list))
        add_applicant_ids = applicant.browse(applicant_ids_int)
        add_applicant_ids.sudo().write({'process_state': 'processed'})
        job = request.env['hr.job'].sudo().search([('id', '=', job_id)])
        text = "%s %s" % (job.name, job.id)
        result = self.slugify(text)
        return result

    def slugify(self, text):
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        text = re.sub(r'[-\s]+', '-', text)
        return text
    
    @http.route("/website_hr_recruitment/get_countries", type='json', auth='public', website=True)
    def get_countries(self):
        countries = http.request.env['res.country'].sudo().search_read([], ['id', 'name', 'code'])
        return countries
    
    @http.route('/website_hr_recruitment/get_states', type='json', auth='public', website=True)
    def get_states(self, country_id):
        domain = [('country_id', '=', int(country_id))]
        states = http.request.env['res.country.state'].sudo().search_read(domain, ['id', 'name'])
        return states
    
    @http.route('/website_hr_recruitment/check_recent_application_by_id', type='json', auth="public", website=True)
    def check_recent_application_by_id(self, identification_id, job_id):
        date_limit = datetime.now() - timedelta(days=90)
        domain = [('identification_id', '=', identification_id), 
                  ('create_date', '>=', date_limit),
                  ('job_id.website_id', 'in', [http.request.website.id, False])]
        recent_applications = http.request.env['hr.applicant'].sudo().search(domain)
        response = {'applied_same_job': any(a.job_id.id == int(job_id) for a in recent_applications),
                    'applied_other_job': bool(recent_applications)}
        return response

class L10nHnHrWebsiteForm(WebsiteForm):

    def _handle_website_form(self, model_name, **kwargs):
        if model_name == 'hr.applicant':
            user_id = request.env.user
            employee_id = False
            if user_id:
                employee_id = user_id.partner_id.employee_ids
                employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)

            kwargs['partner_name'] = kwargs['firstname']
            if 'firstname2' in kwargs:
                kwargs['partner_name'] = '{0} {1}'.format(kwargs['partner_name'], kwargs['firstname2'])
            kwargs['partner_name'] = '{0} {1}'.format(kwargs['partner_name'], kwargs['lastname'])
            if 'lastname2' in kwargs:
                kwargs['partner_name'] = '{0} {1}'.format(kwargs['partner_name'], kwargs['lastname2'])

            res = super(L10nHnHrWebsiteForm, self)._handle_website_form(model_name, **kwargs)
            id = json.loads(res)
            hr_applicant_id = request.env['hr.applicant'].sudo().search([('id', '=', id['id'])])
            if hr_applicant_id:
                if employee_id:
                    hr_applicant_id.is_internal = True
                    hr_applicant_id.emp_id = employee_id.id
                else:
                    hr_applicant_id.is_internal = False
                
                state_id = request.env['res.country.state'].sudo().search([('id', '=', kwargs['state_id'])])
                
                hr_applicant_id.firstname = kwargs['firstname']
                hr_applicant_id.firstname2 = kwargs['firstname2'] if 'firstname2' in kwargs else False
                hr_applicant_id.lastname = kwargs['lastname']
                hr_applicant_id.lastname2 = kwargs['lastname2'] if 'lastname2' in kwargs else False
                hr_applicant_id.identification_id = kwargs['identification_id']
                hr_applicant_id.state_id = state_id
                hr_applicant_id.city = kwargs['city']
                hr_applicant_id.street = kwargs['street']
                hr_applicant_id.street2 = kwargs['street2'] if 'street2' in kwargs else False
                hr_applicant_id.salary_expected = kwargs['salary_expected']

            return res
        
        return super(L10nHnHrWebsiteForm, self)._handle_website_form(model_name, **kwargs)


class L10nHnHrCustomerPortal(CustomerPortal):

    def home(self, **kw):
        res = super(L10nHnHrCustomerPortal, self).home(**kw)

        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)

        qcontext = res.qcontext.copy()

        if employee_id:
            department_id = request.env['hr.department'].sudo().search([('manager_id', '=', employee_id.id), ('company_id', '=', employee_id.company_id.id) ])
            if department_id:
                qcontext['is_manager'] = True
            else:
                qcontext['is_manager'] = False
            qcontext['is_empl'] = True
        else:
            qcontext['is_empl'] = False
            qcontext['is_manager'] = False
        res.qcontext = qcontext
        return res


class PortalPositionCustom(http.Controller):
    
    @http.route('/create_request_position_hr', methods=["POST"], type="json", auth="user", website=True)
    def create_request_position_hr(self, hr_position_id, qty):
        user_id = request.env.user

        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)

        request_date = datetime.datetime.now()
        manager_id = employee_id.id

        position_id = int(hr_position_id)

        res = request.env['request.new.positions'].sudo().create({
            'request_date': request_date,
            'manager_id': manager_id,
            'position_id': position_id,
            'qty': int(qty),
        })
        return "ok"
    
    @http.route(['/request/position/list'], type='http', auth='user', website=True)
    def render_position_template_list(self, page=0, **kwargs):
        items_per_page = 80
        page = int(page)
        user_id = request.env.user


        employee_id = user_id.partner_id.employee_ids
        employee_id = next((emp for emp in employee_id if emp.company_id == user_id.company_id), None)
        position_ids = request.env['hr.position'].sudo().search([])

        Model =  request.env['request.new.positions'].sudo()

        # Contar el total de elementos
        total_items = Model.search_count([('manager_id', '=', employee_id.id)])

        # Calcular el total de páginas
        total_pages = (total_items - 1) // items_per_page + 1

        # Obtener los elementos para la página actual
        request_position_ids = Model.search([('manager_id', '=', employee_id.id)], offset=page * items_per_page, limit=items_per_page)

        return request.render('l10n_hn_hr_recruitment.template_list_of_position', {
            'position_ids': position_ids,
            'request_position_ids': request_position_ids,
            'page': page,
            'total_pages': total_pages,
        })