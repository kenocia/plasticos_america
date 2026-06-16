# -*- coding: utf-8 -*-
{
    'name': 'KC Comisiones de Ventas',
    'version': '18.0.1.0.13',
    'summary': 'Cálculo de comisiones por empleado según clientes asignados y facturas',
    'description': """
Comisiones de ventas por empleado comisionista, basadas en facturas de cliente
publicadas en un rango de fechas, con exportación Excel y PDF de autorización.
    """,
    'author': 'KENOCIA',
    'website': 'https://kenocia.com/',
    'category': 'Sales',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'hr',
        'account',
        'mail',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'report/sales_commission_report.xml',
        'report/report_action.xml',
        'views/res_partner_views.xml',
        'views/hr_employee_views.xml',
        'views/product_template_views.xml',
        'views/product_category_views.xml',
        'views/account_payment_views.xml',
        'views/sales_commission_views.xml',
        'views/sales_commission_wizard_views.xml',
        'views/sales_commission_payment_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/icon.png'],
    'post_init_hook': 'post_init_hook',
}
