# -*- coding: utf-8 -*-

{
    'name': 'Adelantos de salario del empleado en el portal',
    'version': '18.0.0.2',
    'author': "Easi Coders LLC",
    'website': "",
    "license": "AGPL-3",
    'category': 'Human Resources',
    'summary': 'Personalización de los adelantos de salario por el portal.',
    'depends': ['l10n_hn_salary_advance', 'website', 'portal'],
    'data': [
        'views/advance_portal_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': False,

    'assets': {
        'web.assets_frontend': [
            'l10n_hn_hr_salary_advance_portal/static/src/js/advance_request.js',
        ],
    }
}
