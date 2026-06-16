# -*- coding: utf-8 -*-
{
    'name': "Nómina Honduras",
    'author': "Kenosis Company",
    'summary': 'Módulo de nómina para Honduras con cálculos de IHSS, RAP e ISR',
    'description': """
        Nómina Honduras
        ===============

        Módulo especializado para el cálculo de nómina en Honduras que incluye:

        Características principales:
        * Cálculo automático de IHSS (Instituto Hondureño de Seguridad Social)
        * Cálculo de RAP (Régimen de Aportaciones Privadas)
        * Cálculo de ISR (Impuesto Sobre la Renta)
        * Gestión de beneficios y deducciones personalizadas
        * Historial de cambios salariales y cálculos fiscales
        * Envío automático de vouchers de pago por email
        * Exportación a Excel de reportes de nómina
        * Wizards para asignación masiva de parámetros fiscales

        Funcionalidades incluidas:
        * Configuración de parámetros fiscales hondureños
        * Cálculos automáticos en contratos de empleados
        * Reportes y análisis detallados de nómina
        * Integración completa con el módulo de payroll de Odoo
        * Cumplimiento con la legislación laboral de Honduras
    """,
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'website': 'https://www.cesl.hn',
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr',
        'hr_contract',
        'hr_payroll',
        'hr_payroll_account',
        'mail',
        'base',
        'web',  # Agregado para Odoo 18
        # 'cmc_sales_book',  # Comentado - verificar si es necesario
    ],
    'external_dependencies': {
        'python': [
            'xlsxwriter',  # Para exportación Excel
        ],
    },
    'data': [
        # Seguridad
        'security/ir.model.access.csv',
        'security/hr_hn_assign_benefit_deduction_security.xml',

        # Datos iniciales
        'data/hr_payroll_structure.xml',
        'data/hr_salary_rule.xml',

        # Vistas principales
        'views/hr_hn_ihss_views.xml',
        'views/hr_hn_rap_views.xml',
        'views/hr_hn_isr_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_salary_rule_category_views.xml',

        # Vistas de historial
        'views/hr_hn_salary_history_views.xml',
        'views/hr_hn_ihss_history_views.xml',
        'views/hr_hn_rap_history_views.xml',
        'views/hr_hn_isr_history_views.xml',
        'views/hr_hn_benefit_deduction_history_views.xml',

        # Vistas de extensión
        'views/hr_contract_views.xml',
        'views/hr_department_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',

        # Reportes
        # 'reports/report_payslip.xml',
        # 'reports/isr_report.xml',
        'reports/payment_voucher.xml',

        # Wizards
        'wizard/hr_hn_assign_benefit_deduction_views.xml',
        'wizard/hr_hn_pause_benefit_deduction_views.xml',
        'wizard/hr_hn_delete_benefit_deduction_views.xml',
        'wizard/hr_hn_payroll_report_views.xml',
        'wizard/payrroll_excel_wizard.xml',

        # Menús (debe ir al final para que las acciones estén disponibles)
        'views/menuitem.xml',
    ],
    # 'demo': [
        # 'demo/hr_hn_demo_data.xml',
    # ],
    'assets': {
        'web.assets_backend': [
            'payroll_hn/static/src/components/deductions_report/deductions_report.css',
            'payroll_hn/static/src/components/payroll_report/payroll_report.css',
            'payroll_hn/static/src/components/deductions_report/deductions_report.js',
            'payroll_hn/static/src/components/payroll_report/payroll_report.js',
            'payroll_hn/static/src/xml/deductions_report.xml',
            'payroll_hn/static/src/xml/payroll_report.xml',
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': None,
    'uninstall_hook': None,
    'price': 0.0,
    'currency': 'USD',
}
