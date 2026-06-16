{
    'name': "Easi Coders: Honduras Contrato de empleado",
    'version': '18.0.0.1',
    'depends': ['l10n_hn_hr', 'hr_contract', 'portal'],
    'author': "Easi Coders",
    'license': 'OPL-1',
    'category': 'Línea base Honduras/Human Resources/Contract',
    'description': """
    Honduras Payroll Localization
    """,
    'data': [
        "data/email_template.xml",
        # "data/hr_contract_cron_data.xml",
        "data/hr_table_previous_quit_notice_data.xml",
        "data/hr_data.xml",
        "data/hr_positiion_data.xml",
        "security/ir.model.access.csv",
        "views/hr_employee_view.xml",
        "views/hr_contract_view.xml",
        "views/res_company_hn_config_view.xml",
        "views/hr_quit_request.xml",
        "views/hr_quit_request_seq.xml",
        "views/hr_position_view.xml",
        "views/hr_job_views.xml",
        'views/templates.xml',
        'views/quit_portal_views.xml',
    ],
    "development_status": "Beta",
    "application": True,
    "installable": True,
    'assets': {
        'web.assets_frontend': [
            'l10n_hn_hr_contract/static/src/js/quit_request.js',
        ],
    }
}
