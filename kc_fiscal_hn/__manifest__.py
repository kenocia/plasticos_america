# -*- coding: utf-8 -*-
{
    'name': "Kenocia Fiscal Honduras",

    'summary': """
        Módulo que contiene lo necesario para control fiscal de Honduras""",

    'description': """
        Módulo que contiene lo necesario para control fiscal de Honduras:
        - Reportes fiscales (SAR, boletas, guías de remisión)
        - Secuencias de facturación
        - Impuestos y configuraciones fiscales
        - Wizards de reportes Excel
        - Vistas de contabilidad extendidas
        - Compatible con regulaciones fiscales hondureñas
    """,

    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '18.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'sale', 'stock', 'web', 'sale_stock', 'account_reports'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/fiscal_data.xml',
        #'views/res_partner.xml',
        'views/account_invoice_view.xml',
        'views/account_journal.xml',
        'views/account_move.xml',
        'views/account_tax.xml',
        'views/account_payment.xml',
        'views/ir_sequence.xml',
        'views/account_move_menu_debit_note.xml',
        'wizard/report_dmc_excel.xml',
        'wizard/report_invoice_details_excel.xml',
        'wizard/report_sales_excel.xml',
        'wizard/account_move_warning_wizard.xml',
        'wizard/sequence_alerts_wizard.xml',
        'wizard/fiscal_validation_wizard.xml',
        'wizard/report_sales_sar.xml',
        'wizard/report_purchases_sar.xml',
        'wizard/report_retentions_sar.xml',
        'wizard/report_exemptions_sar.xml',
        'wizard/reset_sequence.xml',
        'wizard/resolve_alert.xml',
        'views/sequence_alert.xml',
        'views/sequence_audit.xml',
        'views/menu.xml',
        'views/product_template.xml',
        'views/stock_move_line.xml',
        'views/stock_picking.xml',
        'views/res_company_views.xml',
        'report/report_invoice_sar.xml',
        'report/report_credit_note.xml',
        'report/custom_layout.xml',
        'report/Paper_format.xml',
        'report/report_comprobante_retencion.xml',
        'report/report_boleta_compra.xml',
        'report/report_guia_remision.xml',
        'report/aged_partner_balance.xml',
        'report/action_report.xml',
        'report/report_journal_entry.xml',
    ],
    
    
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
    
    # Additional metadata
    'images': [],
    'demo': [],
    'test': [],
    'css': [],
    'js': [],
    'qweb': [],
    
    # Module specific data
    'currency': 'HNL',
    'country': 'HN',
    'language': 'es_HN',
    
    # Support information
    'support': 'support@kenocia.com',
    'maintainer': 'KENOCIA',
    'contributors': ['KENOCIA Team'],
    
    # Technical information
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
    
    # Module lifecycle
    'pre_init_hook': None,
    'post_init_hook': None,
    'uninstall_hook': None,
}
