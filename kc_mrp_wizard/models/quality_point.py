# -*- coding: utf-8 -*-
from odoo import api, models


class QualityPoint(models.Model):
    _inherit = 'quality.point'

    @api.depends('name', 'title')
    def _compute_display_name(self):
        """Siempre mostrar referencia + título (el estándar solo lo hace en asistente on-demand)."""
        for record in self:
            if record.title:
                record.display_name = f'{record.name} - {record.title}'
            else:
                record.display_name = record.name or ''

    def action_see_spc_control_with_limits(self):
        """Igual dominio que SPC estándar, pero el cliente dibuja varias series (medida + norma + tolerancias)."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'kc_mrp_wizard.quality_check_action_spc_limits'
        )
        if self.test_type == 'measure':
            action['context'] = {
                'group_by': ['name', 'point_id'],
                'graph_mode': 'line',
                'graph_measure': 'measure',
                'graph_spc_limits': True,
            }
        action['domain'] = [('point_id', '=', self.id), ('quality_state', '!=', 'none')]
        return action
