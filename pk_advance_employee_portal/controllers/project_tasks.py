from odoo.tools import json
from odoo.tools.translate import _

from odoo.addons.portal.controllers.portal import pager
from odoo import http
from odoo.http import route, request
from odoo.addons.portal.controllers import portal
from _datetime import datetime


class ProjectTaskPortal(portal.CustomerPortal):


    #redirect the odoo standard project and task routs to our custom
    @http.route(['/my/projects', '/my/tasks'], type='http', auth='user', website=True)
    def block_default_routes(self, **kw):
        return request.redirect('/tasks/my')

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if request.env.user.has_group("pk_advance_employee_portal.ad_group_portal_tasks"):
            if "project_checkout_count" in counters:
                count = request.env["project.task"].sudo().search_count([])
                values["project_checkout_count"] = count
        return values

    @http.route(["/tasks/my", "/tasks/my/page/<int:page>"], type="http", auth="user", website=True)
    def portal_project_tasks_view(self, page=1, **kw):
        Task = request.env["project.task"].sudo()

        user_id = request.env.uid
        # Get parameters
        date_start = request.params.get('date_start')
        date_end = request.params.get('date_end')
        search_in = request.params.get('search_in', 'project_id')
        search_value = request.params.get('search', '').strip()

        # Search fields
        search_input_values = {
            'project_id': {'input': 'project_id', 'label': _('Search by Project'), 'order': 1},
            'task_id': {'input': 'task_id', 'label': _('Search by Task'), 'order': 2},
            'assignee': {'input': 'user_ids', 'label': _('Search by Assignee'), 'order': 3},
            'milestone': {'input': 'milestone_id', 'label': _('Search by Milestone'), 'order': 4},
        }

        # Domain base: show only current user's tasks
        domain = [('user_ids', 'in', [request.uid])]

        # Search filter
        if search_value:
            if search_in == 'project_id':
                domain += [('project_id.name', 'ilike', search_value)]
            elif search_in == 'task_id':
                domain += [('name', 'ilike', search_value)]
            elif search_in == 'assignee':
                domain += [('user_ids.name', 'ilike', search_value)]
            elif search_in == 'milestone':
                domain += [('milestone_id.name', 'ilike', search_value)]
            else:
                domain += ['|', ('name', 'ilike', search_value), ('project_id.name', 'ilike', search_value)]

        # Date filter
        if date_start:
            try:
                start = datetime.strptime(date_start, '%Y-%m-%d').date()
                domain += [('date_deadline', '>=', start)]
            except Exception:
                pass

        if date_end:
            try:
                end = datetime.strptime(date_end, '%Y-%m-%d').date()
                domain += [('date_deadline', '<=', end)]
            except Exception:
                pass

        # Pagination
        task_count = Task.search_count(domain)
        pager_data = pager(url="/tasks/my", total=task_count, page=page, step=self._items_per_page)

        tasks = Task.search(domain, limit=self._items_per_page, offset=pager_data['offset'])

        # Prepare values
        values = self._prepare_portal_layout_values()
        values.update({
            "checkouts": tasks,
            "page_name": "project_tasks",
            "default_url": "/tasks/my",
            "pager": pager_data,
            "user": request.env.user,
            "search_input_values": search_input_values,
            "search_in": search_in,
            "search": search_value,
            "date_start": date_start,
            "date_end": date_end,
        })
        return request.render("pk_advance_employee_portal.ad_project_tasks_temp_id", values)


    # view task controller
    @http.route(['/task/my/<int:task_id>'], type='http', auth='user', website=True)
    def portal_task_view(self, task_id, **kw):
        task = request.env['project.task'].sudo().browse(task_id)

        values = {
            'task': task,
            'projects': request.env['project.project'].sudo().search([]),
            'milestones': request.env['project.milestone'].sudo().search([]),
            'stages': request.env['project.task.type'].sudo().search([]),
            'users': request.env['res.users'].sudo().search([]),
            'partner': request.env['res.partner'].sudo().search([]),
        }
        return request.render("pk_advance_employee_portal.ad_portal_task_view", values)

    # update task from portal
    @http.route(['/update/tasks/<int:task_id>/update'], type='http', auth='user', methods=['POST'], website=True,
                csrf=False)
    def update_task(self, task_id, **post):
        task = request.env['project.task'].sudo().with_context(
            allowed_portal_fields=['task_properties']
        ).browse(task_id)

        if not task.exists():
            return request.redirect('/tasks/my/')

        if task.stage_id.fold:
            return request.redirect('/tasks/my/')

        vals = {}

        if post.get('name'):
            vals['name'] = post['name']

        if post.get('project_id'):
            vals['project_id'] = int(post['project_id'])

        if post.get('milestone_id'):
            vals['milestone_id'] = int(post['milestone_id'])

        if post.get('stage_id'):
            vals['stage_id'] = int(post['stage_id'])

        if post.get('user_ids'):
            vals['user_ids'] = [(6, 0, [int(post['user_ids'])])]

        if post.get('date_deadline'):  # write it **only** if present & not blank
            vals['date_deadline'] = post['date_deadline']

        if post.get('description'):
            vals['description'] = post['description']

        if vals:
            task.write(vals)

        # Handle properties update
        if 'task_properties' in post:
            try:
                vals['task_properties'] = json.loads(post.get('task_properties'))
            except ValueError:
                pass

        task.write(vals)
        return request.redirect('/tasks/my/')