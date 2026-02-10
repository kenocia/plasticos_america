# -*- coding: utf-8 -*-
{
    'name': "KC BCH Tipo de Cambio",
    'summary': "Actualiza automaticamente la tasa BCH",
    'description': """
        Actualizacion automatica diaria de la tasa BCH en res.currency.rate.
        Permite configurar la llave del API y el indicador BCH.
    """,
    'author': "KENOCIA",
    'website': "https://kenocia.com/",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'version': '18.0.1.0.0',
    'depends': ['base', 'account'],
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/res_currency_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
