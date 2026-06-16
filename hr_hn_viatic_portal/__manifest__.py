# -*- coding: utf-8 -*-
{
    'name': "hr_hn_viatic_portal",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",


    'category': 'Human resources',
    'version': '18.0.0.0.2',

    # any module necessary for this one to work correctly
    'depends': ['base','hr_expense', 'account_accountant','website_sale', 'portal'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/hr_expense_views.xml',
        'views/viatic_expense_views.xml',
        'views/hr_expense_sheet_inherit_viatic.xml',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'report/report_viatic.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'license': 'OPL-1',
    'assets': {
            'web.assets_frontend': [
                'hr_hn_viatic_portal/static/src/js/viatic_expense.js',
            ],
        }
}

