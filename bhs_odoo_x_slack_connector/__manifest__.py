# -*- coding: utf-8 -*-
{
    'name': 'Odoo x Slack Connector',
    'version': '1.0',
    'author': 'Bac Ha Software',
    'website': 'https://bachasoftware.com',
    'maintainer': 'Bac Ha Software',
    'category': 'Extra Tools',
    'summary': "This module helps businesses improve communication efficiency, ensuring that important Odoo notifications are instantly delivered to the right Slack channels or users.",
    'description': "This module helps businesses improve communication efficiency, ensuring that important Odoo notifications are instantly delivered to the right Slack channels or users.",
    'depends': ['base_setup','mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/slack_connector.xml',
        'views/slack_user_config.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {
        'python': ['slackclient', 'html-slacker'],
    },
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
    'price': '26.00',
    'currency': 'USD',
}