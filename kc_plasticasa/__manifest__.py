# -*- coding: utf-8 -*-
{
    'name': "KC Plasticasa",

    'summary': """
        Módulo para gestión de productos de Plasticasa""",

    'description': """
        Módulo para gestión de productos de Plasticasa:
        - Campos adicionales en productos (número de rosca, máquina, gramaje, unidades x fardo)
        - Administración de números de bolsas asignadas a productos
    """,

    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',

    'category': 'Sales',
    'version': '18.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'sale', 'purchase', 'stock', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_template.xml',
        'views/uom_secondary_views.xml',
        'report/report_payment_voucher_action.xml',
        'report/report_payment_voucher.xml',
        'report/report_batch_payment_action.xml',
        'report/report_batch_payment.xml',
        'views/payment_batch_views.xml',
        'views/sales_invoices_report_wizard_view.xml',
        'views/account_batch_payment_report_view.xml',
        'views/account_payment_report_view.xml',
        'views/account_move_actions.xml',
        'data/payment_batch_sequence.xml',
        'data/payment_batch_wizard_sequence.xml',
        'report/report_sales_invoices_action.xml',
        'report/report_sales_invoices.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}

