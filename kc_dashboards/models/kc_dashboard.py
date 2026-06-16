# -*- coding: utf-8 -*-

from odoo import api, models, _


class KcDashboard(models.AbstractModel):
    _name = 'kc.dashboard'
    _description = 'KenoCia Dashboards'

    @api.model
    def get_kc_dashboard_items(self):
        return [
            {
                'id': 'sales',
                'name': _('Ventas'),
                'icon': 'fa-line-chart',
            },
            {
                'id': 'general_inventory',
                'name': _('Inventario General'),
                'icon': 'fa-cubes',
            },
            {
                'id': 'inventory_movements',
                'name': _('Movimientos de inventario'),
                'icon': 'fa-exchange',
            },
        ]
