# -*- coding: utf-8 -*-
{
    'name': 'Indicadores',
    'summary': 'Dashboards personalizados e interactivos',
    'description': """
        Dashboards personalizados en Odoo con componentes OWL interactivos.
        El primer dashboard muestra ventas diarias basadas en pedidos de venta.
        El segundo dashboard muestra inventario general con stock, valor y alertas.
        El tercer dashboard muestra movimientos de inventario del día.
    """,
    'author': 'KENOCIA',
    'website': 'https://kenocia.com/',
    'license': 'LGPL-3',
    'category': 'Reporting',
    'version': '18.0.1.0.62',
    'depends': [
        'account',
        'sale',
        'sale_stock',
        'stock',
        'web',
    ],
    'data': [
        'security/kc_dashboards_security.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kc_dashboards/static/src/dashboard_app/dashboard_app.css',
            'kc_dashboards/static/src/sales_dashboard/sales_dashboard.css',
            'kc_dashboards/static/src/inventory_dashboard/inventory_dashboard.css',
            'kc_dashboards/static/src/movements_dashboard/movements_dashboard.css',
            'kc_dashboards/static/src/xml/sales_dashboard.xml',
            'kc_dashboards/static/src/xml/inventory_dashboard.xml',
            'kc_dashboards/static/src/xml/movements_dashboard.xml',
            'kc_dashboards/static/src/sales_dashboard/sales_dashboard.js',
            'kc_dashboards/static/src/inventory_dashboard/inventory_dashboard.js',
            'kc_dashboards/static/src/movements_dashboard/movements_dashboard.js',
            'kc_dashboards/static/src/xml/dashboard_app.xml',
            'kc_dashboards/static/src/dashboard_app/dashboard_app.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
