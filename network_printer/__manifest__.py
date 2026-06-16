# -*- coding: utf-8 -*-
{
    'name': "KC Network Printer",
    'summary': """
        Configuración de impresoras en red para Odoo""",
    'description': 'Módulo para configurar impresoras en red. Configuración de impresoras por IP. Tipos de impresora: Listín y A4/Carta. Envío directo de impresión a IP configurada. Soporte para protocolos RAW, IPP y LPR.',
    'author': 'KC Development',
    'website': 'https://www.kenocia.com',
    'category': 'Tools',
    'version': '18.0.1.0.0',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/network_printer_views.xml',
        'wizard/printer_test_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    # pycups es opcional - el código maneja su ausencia
    # Para usar IPP, instalar con: pip install pycups
}

