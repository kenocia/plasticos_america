# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    kc_handheld_state_label = fields.Char(
        string='Estado handheld',
        compute='_compute_kc_handheld_state_label',
    )
    kc_handheld_state_group = fields.Selection(
        selection=[
            ('waiting', 'En espera'),
            ('assigned', 'Disponible'),
        ],
        string='Grupo handheld',
        compute='_compute_kc_handheld_state_group',
        search='_search_kc_handheld_state_group',
        store=True,
    )

    def _compute_kc_handheld_state_label(self):
        labels = {
            'waiting': _('En espera'),
            'confirmed': _('En espera'),
            'assigned': _('Disponible'),
        }
        for picking in self:
            picking.kc_handheld_state_label = labels.get(picking.state, picking.state or '')

    @api.depends('state')
    def _compute_kc_handheld_state_group(self):
        for picking in self:
            if picking.state == 'assigned':
                picking.kc_handheld_state_group = 'assigned'
            elif picking.state in ('waiting', 'confirmed'):
                picking.kc_handheld_state_group = 'waiting'
            else:
                picking.kc_handheld_state_group = False

    def _search_kc_handheld_state_group(self, operator, value):
        if operator not in ('=', 'in'):
            return []
        values = value if isinstance(value, (list, tuple)) else [value]
        states = []
        if 'waiting' in values:
            states.extend(['waiting', 'confirmed'])
        if 'assigned' in values:
            states.append('assigned')
        return [('state', 'in', states)] if states else [('id', '=', False)]

    def action_kc_logistics_handheld_open_gs1_scan(self):
        self.ensure_one()
        perms = self.env['res.users'].kc_logistics_handheld_permissions_for_uid()
        if not perms['despachos']:
            raise UserError(_('No tiene permiso para operar despachos en la app Logística.'))
        return self.action_kc_open_gs1_scan_wizard()

    def action_kc_logistics_handheld_back_to_menu(self):
        """Vuelve al menú principal de la app Logística (botón cabecera kanban)."""
        return self.env['kc.logistics.handheld.launcher'].action_open_logistics_launcher()
