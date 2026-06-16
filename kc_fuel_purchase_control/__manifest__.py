{
    'name': 'KC Fuel Purchase Control',
    'version': '18.0.1.0.0',
    'summary': 'Control de combustible basado en compras y facturas de proveedor',
    'description': """
KC Fuel Purchase Control
========================
Módulo para control de combustible vía vales internos, órdenes de compra y facturas de proveedor,
con historial de consumo y trazabilidad completa.
""",
    'author': 'KENOCIA',
    'website': 'https://kenocia.com/',
    'category': 'Purchases',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'account',
        'mail',
        'analytic',
        'hr',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'report/fuel_voucher_report.xml',
        'report/fuel_voucher_templates.xml',
        'views/fuel_vehicle_views.xml',
        'views/fuel_voucher_views.xml',
        'views/fuel_consumption_log_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}

