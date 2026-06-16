# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

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
    pin_timeout_minutes = fields.Integer(
        string='Revalidar PIN cada (min)',
        default=15,
        help='Tiempo máximo de inactividad antes de volver a pedir PIN en la vista tablet. 0 = sin caducidad.',
    )
    validate_alert_quality = fields.Boolean(
        string='Validar alerta de calidad',
        default=True,
        help='Si está activo, se validará la alerta de calidad antes de poder operar.',
    )
    validate_alert_maintenance = fields.Boolean(
        string='Validar alerta de mantenimiento',
        default=True,
        help='Si está activo, se validará la alerta de mantenimiento antes de poder operar.',
    )

    kc_tablet_creates_pt_lot = fields.Boolean(
        string='Genera lote de PT (tablet)',
        help='Solo un centro con este indicador por lista de materiales. Aquí se crea el lote/etiqueta de producto terminado.',
    )
    kc_label_network_printer_id = fields.Many2one(
        'network.printer',
        string='Impresora etiquetas de lote (Zebra/red)',
        domain=[('active', '=', True)],
        help='Impresión directa desde el tablet (RAW puerto 9100, ZPL) de la etiqueta GS1 compatible con Plasticasa. '
             'ZD421 en red (protocolo RAW).',
        check_company=False,
    )

    def action_open_tablet_wizard(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_(
                'Este centro no tiene empleados asignados. Asigne al menos un empleado en "Empleados con acceso" para poder operar.'
            ))
        # Crear explícitamente el wizard para que las líneas de empleado
        # se creen en base de datos y los botones de las líneas puedan usarse
        # sin que Odoo pida "Primero guarde sus cambios".
        wizard = self.env['mrp.tablet.employee.wizard'].create({
            'workcenter_id': self.id,
        })
        return {
            'name': _('Asistente MRP'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.tablet.employee.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('kc_mrp_wizard.mrp_tablet_employee_wizard_form').id,
            'target': 'new',
            'res_id': wizard.id,
        }

    def action_open_supervisor_consume_prelabel(self):
        """Registro de pre-etiquetas sin sesión PIN (supervisores)."""
        self.ensure_one()
        if not self.kc_tablet_creates_pt_lot:
            raise UserError(_(
                'Este centro no tiene activo «Genera lote de PT (tablet)». '
                'Solo en esos centros se pueden registrar pre-etiquetas desde aquí.'
            ))
        wizard = self.env['mrp.supervisor.consume.prelabel.wizard'].create({
            'workcenter_id': self.id,
        })
        return {
            'name': _('Registrar pre-etiquetas (supervisor)'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.supervisor.consume.prelabel.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

