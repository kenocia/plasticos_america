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
    'version': '18.0.1.11.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'hr',
        'product',
        'sale',
        'sale_stock',
        'purchase',
        'stock',
        'stock_barcode',
        'barcodes_gs1_nomenclature',
        'stock_account',
        'account',
        'network_printer',
    ],

    # always loaded
    'data': [
        'security/physical_lot_scan_security.xml',
        'security/ir.model.access.csv',
        'data/physical_lot_scan_sequence.xml',
        'views/product_template.xml',
        'views/stock_lot_views.xml',
        'views/res_company_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_picking_views.xml',
        'views/gs1_picking_scan_wizard_views.xml',
        'views/physical_lot_scan_views.xml',
        'views/uom_secondary_views.xml',
        'wizard/product_movement_report_wizard_views.xml',
        'wizard/kc_net_sales_report_views.xml',
        'wizard/kc_lot_label_print_wizard_views.xml',
        'report/report_payment_voucher_action.xml',
        'report/report_payment_voucher.xml',
        'report/report_batch_payment_action.xml',
        'report/report_batch_payment.xml',
        'views/payment_batch_views.xml',
        'views/sales_invoices_report_wizard_view.xml',
        'views/account_batch_payment_report_view.xml',
        'views/account_payment_report_view.xml',
        'views/account_move_actions.xml',
        'views/res_partner_views.xml',
        'data/payment_batch_sequence.xml',
        'data/payment_batch_wizard_sequence.xml',
        'report/report_sales_invoices_action.xml',
        'report/report_sales_invoices.xml',
        'report/kc_lot_label_templates.xml',
        'report/kc_lot_label_report.xml',
    ],

    'assets': {
        'web.assets_backend': [
            (
                'after',
                'stock_barcode/static/src/models/barcode_picking_model.js',
                'kc_plasticasa/static/src/js/kc_plasticasa_barcode_patches.js',
            ),
            'kc_plasticasa/static/src/js/kc_gs1_scan_form.js',
            'kc_plasticasa/static/src/js/kc_gs1_scan_field.js',
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,
}

