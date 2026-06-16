# -*- coding: utf-8 -*-

{
    'name': 'Préstamos del empleado en el portal',
    'version': '18.0.0.2',
    'author': "Easi Coders LLC",
    'website': "",
    "license": "AGPL-3",
    'category': 'Human Resources',
    'summary': 'Personalización de los préstamos por el portal.',
    'depends': ['l10n_hn_loan', 'website', 'portal'],
    'data': [
        'views/loan_portal_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': False,

    'assets': {
        'web.assets_frontend': [
            'l10n_hn_hr_loan_portal/static/src/js/loan_request.js',
        ],
    }
}
