# -*- coding: utf-8 -*-
{
    'name': "Custom Portal HR Expense",

    'summary': "Permite a los usuarios solicitar y visualizar gastos desde el portal",

    'description': """
Long description of module's purpose
    """,

    'author': "easicoders",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '18.0.0.0.3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr', 'hr_expense', 'portal'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/expense_portal_templates.xml',
        # 'views/expense_portal_templates_v18.xml',  # Temporalmente desactivado
        'views/expense_portal_menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'license': 'OPL-1',
    'assets': {
        'web.assets_frontend': [
            '/hr_hn_portal_expense/static/src/scss/styles.scss',
            '/hr_hn_portal_expense/static/src/js/list_expense.js',
            # '/hr_hn_portal_expense/static/src/js/expense_owl.js',  # Temporalmente desactivado
            # '/hr_hn_portal_expense/static/src/js/expense_portal_init.js',  # Temporalmente desactivado
            # '/hr_hn_portal_expense/static/src/xml/expense_form_template.xml',  # Temporalmente desactivado
        ],
    }
}

