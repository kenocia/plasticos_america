# -*- coding: utf-8 -*-
###################################################################################

###################################################################################
{
    'name': 'Open Easi Coders Advance Salary',
    'version': '18.0.0.1',
    'summary': 'Advance Salary In HR',
    'description': """
        Le ayuda a gestionar las solicitudes de adelantos de salario del personal de su empresa.
        """,
    'category': 'Línea base Bolivia/Human Resources/Payroll',
    'live_test_url': '',
    'author': "Easi Coders",
    'company': 'Easi Coders',
    'maintainer': 'Easi Coders',
    'website': "",
    'depends': [
        'l10n_hn_hr_payroll', 'hr', 'account', 'hr_contract', 'l10n_hn_loan',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/salary_structure.xml',
        'views/salary_advance.xml',
        'views/salary_advance_13_14_avo.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

