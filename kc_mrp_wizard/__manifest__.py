# -*- coding: utf-8 -*-
{
    'name': "KenoCia MRP Wizard",
    'summary': "Wizard para MRP por centro de trabajo: PIN, crear lote (fardo), producción parcial, viñeta",
    'description': """
        Wizard para MRP por centro de trabajo:
        - Identificación por PIN y empleados permitidos por workcenter
        - Validación de turno y asistencia (opcional)
        - MO/WO activa por centro de trabajo
        - Crear lote (fardo): producción parcial + lote + impresión viñeta
        - Consumo desde ubicación local del workcenter (FIFO)
        - Historial (mrp.batch_ticket) y reimpresión de viñetas
    """,
    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',
    'category': 'Manufacturing',
    'version': '18.0.1.2.87',
    'post_init_hook': 'post_init_hook',
    'depends': [
        'mrp_workorder',
        'hr',
        'stock',
        'mrp',
        'sale',
        'sale_stock',
        'sale_mrp',
        'quality',
        'quality_control',
        'quality_mrp',
        'maintenance',
        'kc_plasticasa',
        'stock_barcode',
        'network_printer',
        'web',
    ],
    'data': [
        'security/kc_mrp_wizard_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/sequence_data.xml',
        'views/mrp_workcenter_views.xml',
        'views/hr_employee_tablet_security_views.xml',
        'views/mrp_batch_ticket_views.xml',
        'views/mrp_workorder_tablet_views.xml',
        'views/kc_sale_planning_views.xml',
        'views/mrp_bom_line_views.xml',
        'views/mrp_bom_keno_views.xml',
        'views/mrp_production_keno_views.xml',
        'views/stock_lot_keno_views.xml',
        'views/mrp_semi_ticket_views.xml',
        'views/kc_mrp_resin_scrap_type_views.xml',
        'views/mrp_production_stop_type_views.xml',
        'views/quality_alert_views.xml',
        'views/maintenance_view.xml',
        'views/quality_check_views.xml',
        'views/quality_check_graph_views.xml',
        'views/quality_point_views.xml',        
        'wizard/mrp_tablet_wizard_views.xml',
        'wizard/mrp_tablet_reprint_label_wizard_views.xml',
        'wizard/mrp_tablet_selective_manual_production_wizard_views.xml',
        'wizard/kc_mrp_semi_stock_adjustment_wizard_views.xml',
        'views/network_printer_kc_help_views.xml',
        'report/report_batch_ticket_template.xml',
        'report/report_batch_ticket.xml',
        'report/report_mrp_semi_ticket_template.xml',
        'report/report_mrp_semi_ticket.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kc_mrp_wizard/static/src/css/tablet_wizard.css',
            'kc_mrp_wizard/static/src/js/x2many_dialog_ask_changes_patch.js',
            'kc_mrp_wizard/static/src/js/kc_prelabel_scan_form.js',
            'kc_mrp_wizard/static/src/js/kc_prelabel_scan_field.js',
            'kc_mrp_wizard/static/src/js/kc_consult_lot_gs1_scan_form.js',
            'kc_mrp_wizard/static/src/js/kc_consult_lot_gs1_scan_field.js',
            'kc_mrp_wizard/static/src/js/many2one_avatar_no_open_patch.js',
        ],
        # GraphModel vive en web.assets_backend_lazy (graph no está en assets_backend).
        'web.assets_backend_lazy': [
            'kc_mrp_wizard/static/src/js/graph_model_spc_limits.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
