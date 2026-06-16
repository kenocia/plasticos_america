# -*- coding: utf-8 -*-

from odoo import api, models


class KcLogisticsHandheldLauncher(models.Model):
    _inherit = 'kc.logistics.handheld.launcher'

    @api.model
    def _handheld_window_action(self, xml_id):
        """ir.actions.act_window solo es legible por base.group_system; operadores handheld no."""
        return self.env['ir.actions.act_window']._for_xml_id(xml_id)

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
