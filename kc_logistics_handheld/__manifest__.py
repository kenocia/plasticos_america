# -*- coding: utf-8 -*-
{
    'name': 'KC Logística Handheld',
    'version': '18.0.1.2.1',
    'summary': 'App Logística con accesos handheld para despachos, internos y toma física',
    'description': """
App Logística para operación en handheld:
- Despachos GS1 (kanban de entregas en espera/disponible)
- Operaciones internas GS1 por lotes
- Toma física previo
Permisos configurables por usuario mediante campos booleanos.
    """,
    'author': 'KENOCIA',
    'website': 'https://kenocia.com/',
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'stock',
        'barcodes',
        'kc_plasticasa',
    ],
    'data': [
        'security/kc_logistics_handheld_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/stock_picking_type_views.xml',
        'views/internal_lot_scan_log_views.xml',
        'views/internal_lot_transfer_wizard_views.xml',
        'views/logistics_handheld_launcher_views.xml',
        'views/stock_picking_handheld_kanban_views.xml',
        'views/res_users_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kc_logistics_handheld/static/src/css/logistics_handheld.css',
            'kc_logistics_handheld/static/src/js/kc_internal_gs1_scan_form.js',
            'kc_logistics_handheld/static/src/js/kc_internal_gs1_scan_field.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
