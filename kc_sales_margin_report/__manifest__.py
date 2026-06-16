# -*- coding: utf-8 -*-
{
    'name': 'Reporte margen de ventas (Excel)',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Reporte Excel de margen de ventas desde facturas y notas de crédito publicadas',
    'description': """
Margen de ventas en Excel (multi-compañía): detalle por línea de factura,
resúmenes por cliente, vendedor, producto, categoría y mes. Costo estándar
actual (product.standard_price). Incluye notas de crédito en negativo.
    """,
    'author': 'KC',
    'depends': [
        'account',
        'stock',
    ],
    'data': [
        'security/sales_margin_report_security.xml',
        'security/ir.model.access.csv',
        'wizard/sales_margin_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
