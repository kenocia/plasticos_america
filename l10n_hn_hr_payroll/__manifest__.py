{
    'name': "Easi Coders: Honduras empleado",
    'countries': ['hn'],
    'version': '18.0.1.0',
    'depends': [
        'hr_payroll',
        'l10n_hn_hr',
        'l10n_hn_hr_holidays',
        'hr_attendance',
        'l10n_hn_hr_recruitment',
    ],
    'author': "Easi Coders",
    'license': 'OPL-1',
    'category': 'Línea base Honduras/Human Resources/Employees',
    'description': """
    Honduras Payroll Localization
    """,
    'data': [
        'security/ir.model.access.csv',

        "data/hr_payroll_category_data.xml",
        "data/hr_payroll_structure_data.xml",

        "data/hr_salary_rule_14avo.xml",
        "data/hr_salary_rule_13avo.xml",
        "data/hr_salary_rule_month.xml",
        "data/hr_salary_rule_prestaciones.xml",

        "views/hr_payroll_closing_table_view.xml",
        "views/hr_payroll_prestaciones_view.xml",
        'report/paperformat_payroll.xml',
        'report/paperformat_payroll_landscape.xml',
        # 'report/hr_payroll_report.xml',
        "views/hr_payslip_views.xml",
        'views/l10n_hn_monthly_summary_views.xml',
        'views/l10n_hn_bank_summary_views.xml',
        'views/l10n_hn_payroll_summary_views.xml',
        'report/hr_contract_employee_report_views.xml',
        'report/l10n_hn_monthly_summary_template.xml',
        'report/l10n_hn_bank_summary_template.xml',
        'report/l10n_hn_payroll_summary_template.xml',
        'wizard/hr_payroll_payslips_by_employees_views.xml',
        'views/hr_work_entry_views.xml',
        'views/res_bank_view.xml',
    ],
    "development_status": "Beta",
    "application": True,
    "installable": True,
}
