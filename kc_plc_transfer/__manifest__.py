# -*- coding: utf-8 -*-
{
    'name': "PLC Transfer Integration",
    'summary': "Integración PLC (Siemens LOGO! 8 / Gateway) ↔ Odoo para traslados internos automáticos",
    'description': """
        Integración PLC para automatizar traslados internos de inventario:
        - Flujo Receiving: WIP → Receiving PT
        - Flujo Reproceso: PT → WIP
        - Lectura de QR de lotes
        - Validación automática de traslados
        - Bitácora de eventos y trazabilidad
    """,
    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',
    'category': 'Inventory',
    'version': '18.0.1.0.0',
    'depends': ['stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/plc_station_views.xml',
        'views/plc_event_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
