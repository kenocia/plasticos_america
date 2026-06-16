# -*- coding: utf-8 -*-
{
    'name': "Easi Coders: Recruitment",
    'version': '18.0.0.1',
    'author': "Easi Coders",
    'license': 'LGPL-3',
    'summary': "Selección y reclutamiento",
    'description': """
Long description of module's purpose
    """,
    'website': "https://www.yourcompany.com",

    'category': 'Human Resources/Recruitment',
    # any module necessary for this one to work correctly
    'depends': [
        'website_hr_recruitment',
        'hr_contract',
        'portal',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/hr_job_views.xml',
        'views/hr_applicant_views.xml',
        # 'views/templates.xml',
        'views/res_company.xml',
        'views/new_request_position.xml',
        'views/hr_contract_view.xml',
        'data/data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'assets': {
        'web.assets_frontend': [
            '/l10n_hn_hr_recruitment/static/src/js/list_applicant.js',
            '/l10n_hn_hr_recruitment/static/src/js/position_request.js',
            '/l10n_hn_hr_recruitment/static/src/js/website_hr_applicant_form.js',
        ],
    }
}

