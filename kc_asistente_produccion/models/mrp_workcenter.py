# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    # Empleados permitidos: se usa el campo employee_ids de mrp_workorder (si está instalado).
    # Ubicación de consumo: viene de la MO (location_src_id), no se duplica en el centro.
    require_pin = fields.Boolean(
        string='Exigir PIN',
        default=True,
        help='Exigir validación por PIN para acceder al asistente.',
    )
    enforce_shift = fields.Boolean(
        string='Exigir turno y asistencia',
        default=True,
        help='Si está activo, el empleado debe estar en turno y con asistencia abierta (check-in).',
    )
    # Cantidad por lote: se obtiene de la lista de materiales (BOM) de la MO, campo product_qty.

    def action_open_tablet_wizard(self):
        self.ensure_one()
        return {
            'name': _('Asistente tablet'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workcenter_id': self.id},
        }
