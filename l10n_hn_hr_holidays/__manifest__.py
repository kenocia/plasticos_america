{
    'name': "Easi Coders: Honduras Ausencia",
    'version': '18.0.0.1',
    'depends': ['l10n_hn_hr_contract', 'hr_holidays', 'hr_work_entry', 'hr_work_entry_holidays'],
    'author': "Easi Coders",
    'license': 'OPL-1',
    'category': 'Línea base Honduras/Human Resources/Employees',
    'description': """
    Honduras Payroll Localization
    """,
    'data': [
        "data/hr_work_entry_type.xml",
        "data/hr_holidays_data.xml",
        "data/hr_vacation_quota_table_data.xml",
        # "data/hr_vacation_cron_data.xml",
        'security/ir.model.access.csv',
        "views/hr_employee_view.xml",
        "views/res_company_hn_config_view.xml",
        "views/hr_leave_views.xml",
        "views/hr_leave_type_views.xml",
    ],
    "development_status": "Beta",
    "application": True,
    "installable": True,
}
