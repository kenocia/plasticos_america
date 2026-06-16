# -*- coding: utf-8 -*-

from odoo import api, models


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    @api.model
    def _kc_tablet_action_workcenter_menu(self):
        """Devuelve la acción del menú de centros tablet sin exigir permiso de Ajustes.

        ``ir.actions.act_window`` solo es legible por ``base.group_system``; los operadores
        del asistente deben poder volver al menú de centros (Salir, PIN caducado, etc.).
        """
        return dict(
            self.env['ir.actions.act_window']._for_xml_id(
                'kc_mrp_wizard.action_mrp_workcenter_tablet'
            )
        )

    def read(self, fields=None, load='_classic_read'):
        action = self.env.ref(
            'kc_mrp_wizard.action_mrp_production_stop_type',
            raise_if_not_found=False,
        )
        if (
            action
            and action.id in self.ids
            and self.env.user.has_group('kc_mrp_wizard.group_kc_mrp_wizard_user')
        ):
            result = super(IrActionsActWindow, self.sudo()).read(fields=fields, load=load)
        else:
            result = super().read(fields=fields, load=load)
        if not action or action.id not in self.ids:
            return result
        company = self.env.company
        domain = ['|', ('company_id', '=', False), ('company_id', '=', company.id)]
        for i, rec in enumerate(self):
            if rec.id == action.id:
                res = result[i] if isinstance(result, list) else result
                if isinstance(res, dict):
                    res['domain'] = domain
                break
        return result
