# -*- coding: utf-8 -*-
{
    'name': "Asistente de Producción (Tablet)",
    'summary': "Wizard tablet por centro de trabajo: PIN, crear lote (fardo), producción parcial, viñeta",
    'description': """
        Asistente de producción para tablet por centro de trabajo:
        - Identificación por PIN y empleados permitidos por workcenter
        - Validación de turno y asistencia (opcional)
        - MO/WO activa por centro
        - Crear lote (fardo): producción parcial + lote + impresión viñeta
        - Consumo desde ubicación local del workcenter (FIFO)
        - Historial (mrp.batch_ticket) y reimpresión
    """,
    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',
    'category': 'Manufacturing',
    'version': '18.0.1.0.0',
    'depends': ['mrp_workorder', 'hr', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/mrp_workcenter_views.xml',
        'views/hr_employee_views.xml',
        'wizard/hr_employee_pin_wizard_views.xml',
        'views/mrp_batch_ticket_views.xml',
        'wizard/mrp_tablet_wizard_views.xml',
        'report/report_batch_ticket_template.xml',
        'report/report_batch_ticket.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
