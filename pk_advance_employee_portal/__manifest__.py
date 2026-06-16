# -*- coding: utf-8 -*-
# Irfan Ullah Odoo Technical developer with hands-on experience
# contact Whatsapp: +923349693796 Email: irfanbcs797@gmail.com
# YouTube: https://www.youtube.com/@irfanullah
{
    'name': "Advance Employee Portal",

    'summary': "Employee Portal, Advance Employee Portal, Employee Sale Portal + Dashboard, Employee Attendance Portal, Employee TimeOff/Leave Portal, PaySlip/PayRoll Portal, Employee Expense Portal, Employee Weekly Schedule Portal, Employee Project Tasks Portal, Employee Profile Portal, All in one Employee Portal ...more",
    'description': "Employee Portal, Advance Employee Portal, Employee Sale Portal + Dashboard, Employee Attendance Portal, Employee TimeOff/Leave Portal, PaySlip/PayRoll Portal, Employee Expense Portal, Employee Weekly Schedule Portal, Employee Project Tasks Portal, Employee Profile Portal, All in one Employee Portal ...more",

    'author': "Irfan Ullah",
    'website': "https://www.youtube.com/@irfanullah",
    'category': 'Portal',
    'license' : 'OPL-1',
    'version': '18.0.0.1',
    'price': '40.00',
    'currency': 'EUR',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management', 'portal', 'hr_holidays', 'hr_expense', 'hr_payroll', 'planning','project', 'hr', 'hr_attendance', 'stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/portal_access.xml',
        'security/user_groups.xml',
        'views/new_menus_in_portal.xml',
        'views/employee_leave_template.xml',
        'views/weekly_schedule_template.xml',
        'views/attendance_templates.xml',
        'views/project_tasks.xml',
        'views/sale_order.xml',
        'views/hr_expense.xml',
        'views/emp_profile.xml',
        'views/pay_slip.xml',
        'views/inherit_backend_views.xml',
    ],
    'images': ['static/description/banner.png'],
}
