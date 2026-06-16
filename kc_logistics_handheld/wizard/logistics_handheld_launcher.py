# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class KcLogisticsHandheldLauncher(models.TransientModel):
    _name = 'kc.logistics.handheld.launcher'
    _description = 'Pantalla inicial Logística Handheld'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        default=lambda self: _('Logística'),
        required=True,
    )
    kc_allow_despachos = fields.Boolean(string='Permite despachos', readonly=True)
    kc_allow_internos = fields.Boolean(string='Permite internos', readonly=True)
    kc_allow_fisico = fields.Boolean(string='Permite físico', readonly=True)

    @api.model
    def _permissions_values(self):
        return self.env['res.users'].kc_logistics_handheld_permissions_for_uid()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        perms = self._permissions_values()
        res.update({
            'kc_allow_despachos': perms['despachos'],
            'kc_allow_internos': perms['internos'],
            'kc_allow_fisico': perms['fisico'],
        })
        return res

    @api.model
    def _handheld_window_action(self, xml_id):
        """ir.actions.act_window solo es legible por base.group_system; operadores handheld no."""
        return self.env['ir.actions.act_window']._for_xml_id(xml_id)

    @api.model
    def _handheld_nav_action(self, action, *, res_id=None):
        """Odoo 18: target=main sustituye la pila de migas (sin launcher técnico encima)."""
        action = dict(action)
        action['target'] = 'main'
        if res_id:
            action['res_id'] = res_id
            action['view_mode'] = 'form'
            action['views'] = [(False, 'form')]
        ctx = action.get('context') or {}
        if isinstance(ctx, dict):
            action['context'] = dict(ctx)
        return action

    @api.model
    def action_open_logistics_launcher(self):
        """Crea el registro transient y abre el formulario con permisos cargados."""
        launcher = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logística'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': launcher.id,
            'target': 'main',
            'views': [(False, 'form')],
        }

    def _check_permission(self, field_name):
        field_map = {
            'kc_logistics_handheld_despachos': 'despachos',
            'kc_logistics_handheld_internos': 'internos',
            'kc_logistics_handheld_fisico': 'fisico',
        }
        if not self._permissions_values().get(field_map[field_name]):
            raise UserError(_('No tiene permiso para acceder a esta operación.'))

    def action_open_despachos(self):
        self._check_permission('kc_logistics_handheld_despachos')
        return self._handheld_nav_action(
            self._handheld_window_action('kc_logistics_handheld.action_kc_logistics_handheld_despachos')
        )

    def action_open_internos(self):
        self._check_permission('kc_logistics_handheld_internos')
        wizard = self.env['kc.internal.lot.transfer.wizard'].create_new()
        return self._handheld_nav_action(
            self._handheld_window_action('kc_logistics_handheld.action_kc_internal_lot_transfer_wizard'),
            res_id=wizard.id,
        )

    def action_open_fisico(self):
        self._check_permission('kc_logistics_handheld_fisico')
        return self._handheld_nav_action(
            self._handheld_window_action('kc_logistics_handheld.action_kc_logistics_handheld_fisico')
        )
