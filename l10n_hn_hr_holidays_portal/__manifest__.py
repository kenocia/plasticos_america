# -*- coding: utf-8 -*-

{
    'name': 'Ausencias del empleado en el portal',
    'version': '18.0.0.2',
    'author': "Easi Coders LLC",
    'website': "",
    "license": "AGPL-3",
    'category': 'Human Resources',
    'summary': 'Personalización de las ausencias para consultarlas por el portal.',
    'depends': ['hr_holidays', 'website', 'portal'],
    'data': [
        'views/leave_request_portal_templates.xml',
        # 'views/leave_portal_templates_v18.xml',  # Temporalmente desactivado
        'views/hr_leave_type_views.xml',
    ],
    'installable': True,
    'application': False,

    'assets': {
        'web.assets_backend': [
        ],
        'web.assets_common': [

        ],
        'web.assets_frontend': [
            # 'l10n_hn_hr_holidays_portal/static/src/js/leave_owl.js',  # Temporalmente desactivado
            # 'l10n_hn_hr_holidays_portal/static/src/js/leave_portal_init.js',  # Temporalmente desactivado
            # 'l10n_hn_hr_holidays_portal/static/src/xml/leave_request_template.xml',  # Temporalmente desactivado
        ],
    },
}
