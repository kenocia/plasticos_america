{
    'name': "Easi Coders: Honduras empleado",
    'version': '18.0.0.1',
    'depends': ['hr','spreadsheet_dashboard'],
    'author': "Easi Coders",
    'license': 'OPL-1',
    'category': 'Línea base Honduras/Human Resources/Employees',
    'description': """
    Honduras Payroll Localization
    """,
    'data': [
        "data/hr_data.xml",
        "data/hr_blood_type.xml",
        "data/sequence_data.xml",
        # "data/hr_employee_cron_data.xml",
        "security/ir.model.access.csv",
        "views/hr_employee_view.xml",
        "views/res_company_hn_config_view.xml",

        "views/hr_family.xml",
        "views/hr_department_view.xml",
        "views/hr_blood_type_view.xml",
        # "views/resource_calendar_views.xml",
        # "views/hr_resource_calendar_type_view.xml",
        "views/bi_employee_family_view.xml",
    ],
    'assets': {
        'web.assets_frontend': [

        ],
        'web.assets_backend': [
            '/l10n_hn_hr/static/src/js/birthday_dashboard.js',
            '/l10n_hn_hr/static/src/xml/birthday_dashboard.xml',
        ],
    },

    "development_status": "Beta",
    "application": True,
    "installable": True,
}
